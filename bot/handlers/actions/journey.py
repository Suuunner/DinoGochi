
from time import time

from telebot.types import (CallbackQuery, InlineKeyboardMarkup, InputMedia,
                           Message)

from bot.config import mongo_client
from bot.exec import bot
from bot.modules.data_format import list_to_inline, seconds_to_str
from bot.modules.dinosaur import Dino, end_journey
from bot.modules.dinosaur import start_journey as action_journey
from bot.modules.images import dino_journey
from bot.modules.item import counts_items
from bot.modules.journey import all_log, generate_event_message
from bot.modules.localization import get_data, t, get_lang
from bot.modules.markup import cancel_markup, markups_menu as m
from bot.modules.quests import quest_process
from bot.modules.states_tools import ChooseStepState
from bot.modules.user import User
from random import randint
from bot.modules.over_functions import send_message

dinosaurs = mongo_client.dinosaur.dinosaurs
journey_task = mongo_client.dino_activity.journey

premium_loc = ['magic-forest']

async def journey_start_adp(return_data: dict, transmitted_data: dict):
    userid = transmitted_data['userid']
    lang = transmitted_data['lang']
    chatid = transmitted_data['chatid']
    dino: Dino = transmitted_data['last_dino']
    friend = transmitted_data['friend']
    location = return_data['location']
    time_key = return_data['time_key']
    last_mess_id = transmitted_data['steps'][-1]['bmessageid']
    
    data_time = get_data(f'journey_start.time_text.{time_key}', lang)
    image = dino_journey(dino.data_id, location, friend)
    await action_journey(dino._id, userid, data_time['time'], location)

    loc_name = get_data(f'journey_start.locations.{location}', lang)['name']
    time_text = data_time['text']
    text = t('journey_start.start', lang, 
             loc_name=loc_name, time_text=time_text)

    await bot.edit_message_media(
        InputMedia(
            type='photo', media=image, caption=text),
        chatid, last_mess_id)
    await send_message(chatid, t('journey_start.start_2', lang), reply_markup= await m(userid, 'last_menu', lang))

async def start_journey(userid: int, chatid: int, lang: str, 
                        friend: int = 0):
    user = await User().create(userid)
    last_dino = await user.get_last_dino()
    content_data = get_data('journey_start', lang)

    text, a = content_data['ask_loc'], 1
    buttons = {}
    cc = randint(1, 1000)
    cc2 = randint(1, 1000)

    for key, dct in content_data['locations'].items():
        text += f"*{a}*. {dct['text']}\n\n"
        if await user.premium or key not in premium_loc:
            buttons[dct['name']] = f'chooseinline {cc} {key}'
        a += 1

    text_complexity, buttons_complexity = '', []
    comp = content_data['complexity']
    text_complexity = comp['text']
    buttons_complexity.append({comp['button']: 'journey_complexity'})

    m1_reply = list_to_inline(buttons_complexity)
    m2_reply = list_to_inline([buttons], 2)

    await send_message(chatid, text_complexity, 
                           reply_markup=m1_reply)

    buttons_time = [{}, {}, {}]
    b = 2
    for key, dct in content_data['time_text'].items():
        if len(buttons_time[2 - b].keys()) >= b + 1: b -= 1
        buttons_time[2 - b][dct['text']] = f'chooseinline {cc2} {key}'

    m3_reply = list_to_inline(buttons_time)

    steps = [
        {"type": 'inline', "name": 'location', "data": {'custom_code': cc}, 
         "image": 'images/actions/journey/preview.png',
         "message": {"caption": text, "reply_markup": m2_reply}
        },
        {"type": 'inline', "name": 'time_key', "data": {'custom_code': cc2}, 
         "message": {"caption": content_data['time_info'], "reply_markup": m3_reply}
        }
    ]

    await ChooseStepState(journey_start_adp, userid, chatid, lang, steps, 
                          {'last_dino': last_dino, "edit_message": True, 'friend': friend, 'delete_steps': True})
    await send_message(chatid, t('journey_start.cancel_text', lang), 
                           reply_markup=cancel_markup(lang))

@bot.message_handler(pass_bot=True, text='commands_name.actions.journey', 
                     nothing_state=True)
async def journey_com(message: Message):
    userid = message.from_user.id
    lang = await get_lang(message.from_user.id)
    chatid = message.chat.id

    await start_journey(userid, chatid, lang)

@bot.callback_query_handler(pass_bot=True, func=
                            lambda call: call.data.startswith('journey_complexity'), private=True)
async def journey_complexity(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    chatid = callback.message.chat.id

    text = t('journey_complexity', lang)
    await send_message(chatid, text, parse_mode='Markdown')

@bot.message_handler(pass_bot=True, text='commands_name.actions.events')
async def events(message: Message):
    userid = message.from_user.id
    lang = await get_lang(message.from_user.id)
    chatid = message.chat.id

    user = await User().create(userid)
    last_dino = await user.get_last_dino()
    if last_dino:
        journey_data = await journey_task.find_one({'dino_id': last_dino._id})
        last_event = None

        if journey_data:
            st = journey_data['journey_start']
            journey_time = seconds_to_str(int(time()) - st, lang)
            loc = journey_data['location']
            loc_name = get_data(f'journey_start.locations.{loc}', lang)['name']
            col = len(journey_data['journey_log'])

            if journey_data['journey_log']:
                last_event = await generate_event_message(journey_data['journey_log'][-1], lang, journey_data['_id'], True)

            text = t('journey_last_event.info', lang, journey_time=journey_time, location=loc_name, col=col, last_event=last_event)
            button_name = t('journey_last_event.button', lang)
            if last_event:
                text += '\n\n' + t('journey_last_event.last_event', lang, last_event=last_event)

            await send_message(chatid, text, parse_mode='html', reply_markup=list_to_inline(
                [{button_name: f'journey_stop {last_dino.alt_id}'}]))
        else:
            await send_message(chatid, '❌', reply_markup= await m(userid, 'last_menu', lang))

@bot.callback_query_handler(pass_bot=True, func=
                            lambda call: call.data.startswith('journey_stop'))
async def journey_stop(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    chatid = callback.message.chat.id
    code = callback.data.split()[1]

    dino = await dinosaurs.find_one({'alt_id': code})
    if dino and dino['status'] == 'journey':
        await bot.edit_message_reply_markup(chatid, callback.message.id, 
                                   reply_markup=InlineKeyboardMarkup())
        data = await journey_task.find_one({'dino_id': dino['_id']})
        await end_journey(dino['_id'])
        if data:
            await quest_process(data['sended'], 'journey', (int(time()) - data['journey_start']) // 60)
            await send_logs(data['sended'], lang, data, dino['name'])

async def send_logs(chatid: int, lang: str, data: dict, dino_name: str):
    logs = data['journey_log']
    if logs:
        for i in await all_log(logs, lang, data['_id']):
            await send_message(chatid, i, parse_mode='html')

    items_text = '-'
    coins = data['coins']
    items = data['items']
    j_time = seconds_to_str(int(time()) - data['journey_start'], lang)

    if items: items_text = counts_items(items, lang)
    text = t('journey_log', lang, coins=coins, 
             items=items_text, time=j_time, col=len(logs), name=dino_name)
    await send_message(chatid, text, reply_markup= await m(chatid, 'actions_menu', lang, True))