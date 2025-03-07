from time import time

from telebot import types
from telebot.types import Message

from bot.config import mongo_client
from bot.const import GAME_SETTINGS
from bot.exec import bot
from bot.modules.accessory import check_accessory
from bot.modules.data_format import (list_to_keyboard, near_key_number,
                                     seconds_to_str, user_name, list_to_inline)
from bot.modules.dinosaur import Dino, Egg, dead_check
from bot.modules.events import get_event
from bot.modules.inline import dino_profile_markup, inline_menu
from bot.modules.item import AddItemToUser, get_name
from bot.modules.localization import get_data, t, get_lang
from bot.modules.markup import confirm_markup
from bot.modules.markup import markups_menu as m
from bot.modules.states_tools import (ChooseConfirmState, ChooseDinoState,
                                      ChooseOptionState)
from bot.modules.user import User, premium
from bot.modules.kindergarten import check_hours, m_hours, hours_now, minus_hours, dino_kind
from bot.modules.over_functions import send_message

collecting_task = mongo_client.dino_activity.collecting
game_task = mongo_client.dino_activity.game
dino_mood = mongo_client.dinosaur.dino_mood
dinosaurs = mongo_client.dinosaur.dinosaurs
dino_owners = mongo_client.dinosaur.dino_owners
journey_task = mongo_client.dino_activity.journey

async def dino_profile(userid: int, chatid:int, dino: Dino, lang: str, custom_url: str):
    text = ''

    text_rare = get_data('rare', lang)
    replics = get_data('p_profile.replics', lang)
    status_rep = t(f'p_profile.stats.{dino.status}', lang)
    joint_dino, my_joint = False, False

    user = await User().create(userid)
    owners = list(await dino_owners.find({'dino_id': dino._id}).to_list(None))

    for owner in owners:
        if owner['owner_id'] == userid and owner['type'] == 'add_owner':
            joint_dino = True
        if owner['owner_id'] == userid and owner['type'] == 'owner' and len(owners) >= 2: my_joint = True

    season = await get_event('time_year')
    if 'data' in season:
        season = season['data']['season']
    else: season = 'standart'
    tem = GAME_SETTINGS['events']['time_year'][season]

    stats_text = ''
    # Генерация блока со статистикой
    for i in ['heal', 'eat', 'game', 'mood', 'energy']:
        repl = near_key_number(dino.stats[i], replics[i])
        stats_text += f'{tem[i]} {repl} \[ *{dino.stats[i]}%* ]\n'

    age = await dino.age()
    if age.days == 0:
        age = seconds_to_str(age.seconds, lang)
    else: age = seconds_to_str(age.days * 86400, lang)

    dino_name = dino.name
    if joint_dino: dino_name += t('p_profile.joint', lang)

    kwargs = {
        'em_name': tem['name'], 'dino_name': dino_name,
        'em_status': tem['status'], 'status': status_rep,
        'em_rare': tem['rare'], 'qual': text_rare[dino.quality][1],
        'em_age': tem['age'], 'age': age
    }
    text = t('p_profile.profile_text', lang, formating=False).format(**kwargs)

    if dino.status == 'journey':
        text += '\n\n'
        journey_data = await journey_task.find_one({'dino_id': dino._id})

        if journey_data:
            st = journey_data['journey_start']
            journey_time = seconds_to_str(int(time()) - st, lang)
            loc = journey_data['location']
            loc_name = get_data(f'journey_start.locations.{loc}', lang)['name']
            col = len(journey_data['journey_log'])

            text += t('p_profile.journey.text', lang, 
                      em_journey_act = tem['em_journey_act']) + '\n'
            text += t('p_profile.journey.info', lang, journey_time=journey_time, location=loc_name, col=col)

    if dino.status == 'game':
        data = await game_task.find_one({'dino_id': dino._id})
        text += t(
                f'p_profile.game.text', lang, em_game_act=tem['em_game_act'])
        if data:
            if await check_accessory(dino, 'timer', True):
                end = seconds_to_str(data['game_end'] - int(time()), lang)
                text += t(f'p_profile.game.game_end', lang, end=end)

            duration = seconds_to_str(int(time()) - data['game_start'], lang)
            text += t(
                f'p_profile.game.game_duration', lang, duration=duration)
    
    if dino.status == 'collecting':
        data = await collecting_task.find_one({'dino_id': dino._id})
        if data:
            text += t(
                f'p_profile.collecting.text', lang, em_coll_act=tem['em_coll_act'])
            text += t(
                f'p_profile.collecting.progress.{data["collecting_type"]}', lang,
                now = data['now_count'], max_count=data['max_count'])
            
    text += '\n\n' + stats_text
    # Генерация блока с аксессуарами
    add_blok = False
    acsess = {
        'em_game': tem['ac_game'], 'em_coll': tem['ac_collecting'], 'em_jour': tem['ac_journey'], 'em_sleep': tem['ac_sleep'], 'em_weapon': tem['ac_weapon'], "em_armor": tem['ac_armor'], 'em_backpack': tem['ac_backpack']
    }
    for key, item in dino.activ_items.items():
        if not item:
           acsess[key] = t(f'p_profile.no_item', lang)
        else:
            add_blok = True
            name = get_name(item['item_id'], lang)
            if 'abilities' in item.keys() and 'endurance' in item['abilities'].keys():
               acsess[key] = f'{name} \[ *{item["abilities"]["endurance"]}* ]'
            else: acsess[key] = f'{name}'
                
    menu = dino_profile_markup(add_blok, lang, dino.alt_id, joint_dino, my_joint)
    if add_blok:
        text += t('p_profile.accs', lang, formating=False).format(**acsess)

    # затычка на случай если не сгенерируется изображение
    generate_image = open(f'images/remain/no_generate.png', 'rb')
    msg = await bot.send_photo(chatid, generate_image, text,
                parse_mode='Markdown', reply_markup=menu)

    await send_message(chatid, t('p_profile.return', lang), 
                reply_markup= await m(userid, 'last_menu', lang))
    
    # изменение сообщения с уже нужным изображением
    image = await dino.image(user.settings['profile_view'], custom_url)
    await bot.edit_message_media(
        chat_id=chatid,
        message_id=msg.id,
        media=types.InputMedia(
            type='photo', media=image, 
            parse_mode='Markdown', caption=text),
        reply_markup=menu
        )

async def egg_profile(chatid: int, egg: Egg, lang: str):
    text = t('p_profile.incubation_text', lang, 
             time_end=seconds_to_str(
        egg.remaining_incubation_time(), lang)
        )
    img = egg.image(lang)
    await bot.send_photo(chatid, img, text, 
                         reply_markup=await m(chatid, 'last_menu', language_code=lang))

async def transition(element, transmitted_data: dict):
    userid = transmitted_data['userid']
    chatid = transmitted_data['chatid']
    lang = transmitted_data['lang']
    user = await User().create(userid)
    custom_url = ''

    if user and await user.premium and 'custom_url' in user.settings:
        custom_url = user.settings['custom_url']

    if type(element) == Dino:
        await dino_profile(userid, chatid, element, lang, custom_url)
    elif type(element) == Egg:
        await egg_profile(chatid, element, lang)

@bot.message_handler(pass_bot=True, text='commands_name.dino_profile', is_authorized=True)
async def dino_handler(message: Message):
    userid = message.from_user.id
    lang = await get_lang(message.from_user.id)

    bstatus, status = await ChooseDinoState(transition, userid, message.chat.id, lang, send_error=False) 

    if not bstatus and status == 'cancel':
        if await dead_check(userid):
            await send_message(userid, t(f'p_profile.dialog', lang), reply_markup=inline_menu('dead_dialog', lang))
        else:
            await send_message(userid, t(f'p_profile.no_dino_no_egg', lang))

@bot.callback_query_handler(pass_bot=True, func=lambda call: call.data.startswith('dino_profile'))
async def answer_edit(call: types.CallbackQuery):
    dino_data = call.data.split()[1]
    await bot.delete_state(call.from_user.id, call.message.chat.id)

    userid = call.from_user.id
    chatid = call.message.chat.id
    lang = await get_lang(call.from_user.id)

    trans_data = {
        'userid': userid,
        'chatid': chatid,
        'lang': lang
    }
    dino = await Dino().create(dino_data)
    await transition(dino, trans_data)

@bot.callback_query_handler(pass_bot=True, func=lambda call: call.data.startswith('dino_menu'), private=True)
async def dino_menu(call: types.CallbackQuery):
    split_d = call.data.split()
    action = split_d[1]
    alt_key = split_d[2]

    userid = call.from_user.id
    chatid = call.message.chat.id
    lang = await get_lang(call.from_user.id)

    dino = await dinosaurs.find_one({'alt_id': alt_key})
    if dino:
        res = await dino_owners.find_one({'dino_id': dino['_id'], 
                                    'owner_id': userid})

        if res:
            if action == 'reset_activ_item':
                activ_items = {}
                for key, item in dino['activ_items'].items():
                    if item: activ_items[get_name(item['item_id'], lang)] = [key, item]

                result, sn = await ChooseOptionState(remove_accessory, userid, chatid, lang, activ_items, {'dino_id': dino['_id']})

                if result:
                    reply_buttons = [list(activ_items.keys()), [t(f'buttons_name.cancel', lang)]]

                    reply = list_to_keyboard(reply_buttons, 2)
                    text = t('remove_accessory.choose_item', lang)
                    await send_message(userid, text, reply_markup=reply)

            elif action == 'mood_log':
                mood_list = list(await dino_mood.find(
                    {'dino_id': dino['_id']}).to_list(None))
                mood_dict, text, event_text = {}, '', ''
                res, event_end = 0, 0

                for mood in mood_list:
                    if mood['type'] not in ['breakdown', 'inspiration']:
                    
                        key = mood['action']
                        if key not in mood_dict:
                            mood_dict[key] = {'col': 1, 'unit': mood['unit']}
                        else:
                            mood_dict[key]['col'] += 1
                        res += mood['unit']

                    else:
                        event_text = t(f'mood_log.{mood["type"]}.{mood["action"]}', lang)
                        event_end = mood['end_time'] -mood['start_time'] 

                text = t('mood_log.info', lang, result=res)
                if event_text: 
                    event_time = seconds_to_str(event_end, lang, True)
                    text += t('mood_log.event_info', lang, action=event_text, event_time=event_time)

                text += '\n'

                for key, data_m in mood_dict.items():
                    em = '💚'
                    if data_m['unit'] <= 0: em = '💔'
                    act = t(f'mood_log.{key}', lang)
                    
                    unit = str(data_m['unit'] * data_m['col'])
                    if data_m['unit'] > 0: unit = '+'+unit

                    text += f'{em} {act}: `{unit}` '
                    if data_m['col'] > 1: text += f'x{data_m["col"]}'
                    text += '\n'

                await send_message(userid, text, parse_mode='Markdown')

            elif action == 'joint_cancel':
                # Октазать от совместного динозавра
                text = t('cancle_joint.confirm', lang)
                await send_message(userid, text, parse_mode='Markdown', reply_markup=confirm_markup(lang))
                await ChooseConfirmState(cnacel_joint, userid, chatid, lang, transmitted_data={'dinoid': dino['_id']})

            elif action == 'my_joint_cancel':
                # Октазать от совместного динозавра
                text = t('my_joint.confirm', lang)
                await send_message(userid, text, parse_mode='Markdown', reply_markup=confirm_markup(lang))
                await ChooseConfirmState(cnacel_myjoint, userid, chatid, lang, transmitted_data={'dinoid': dino['_id'], 'user': call.from_user})

            elif action == 'kindergarten':
                if not await premium(userid): 
                    text = t('no_premium', lang)
                    await send_message(userid, text)
                else:
                    total, end = await check_hours(userid)
                    hours = await hours_now(userid)
                    text = t('kindergarten.info', lang,
                             hours_now=m_hours - total,
                             remained=total,
                             days=seconds_to_str(end - int(time()), lang, False, 'hour'),
                             hours=hours, remained_today=6
                             )

                    if dino['status'] == 'kindergarten':
                        reply_buttons = list_to_inline([
                            {
                                t('kindergarten.cancel_name', lang): f'kindergarten stop {alt_key}'
                            }])
                    else:
                        reply_buttons = list_to_inline([
                            {
                                t('kindergarten.button_name', lang): f'kindergarten start {alt_key}'
                            }])
                    await send_message(userid, text, parse_mode='Markdown', 
                                           reply_markup=reply_buttons)


async def cnacel_joint(_:bool, transmitted_data:dict):
    userid = transmitted_data['userid']
    lang = transmitted_data['lang']
    dinoid = transmitted_data['dinoid']

    await dino_owners.delete_one({'dino_id': dinoid, 'owner_id': userid})
    await send_message(userid, '✅', reply_markup= await m(userid, 'last_menu', lang))

async def cnacel_myjoint(_:bool, transmitted_data:dict):
    user = transmitted_data['user']
    userid = user.id
    lang = transmitted_data['lang']
    dinoid = transmitted_data['dinoid']

    res = await dino_owners.find_one({'dino_id': dinoid, 'type': 'add_owner'})
    if res: 
        await dino_owners.delete_one({'_id': res['_id']})
        text = t("my_joint.m_for_add_owner", lang, username=user_name(user))
        await send_message(res['owner_id'], text, reply_markup= await m(userid, 'last_menu', lang))

    await send_message(userid, '✅', reply_markup= await m(userid, 'last_menu', lang))

async def remove_accessory(option: list, transmitted_data:dict):
    userid = transmitted_data['userid']
    lang = transmitted_data['lang']
    dino_id = transmitted_data['dino_id']
    key, item = option
    
    await dinosaurs.update_one({'_id': dino_id}, 
                         {'$set': {f'activ_items.{key}': None}})
    await AddItemToUser(userid, item['item_id'], 1, item['abilities'])

    await send_message(userid, t("remove_accessory.remove", lang), 
                           reply_markup= await m(userid, 'last_menu', lang))

@bot.callback_query_handler(pass_bot=True, func=lambda call: call.data.startswith('kindergarten'), private=True)
async def kindergarten(call: types.CallbackQuery):
    split_d = call.data.split()
    action = split_d[1]
    alt_key = split_d[2]

    userid = call.from_user.id
    chatid = call.message.chat.id
    lang = await get_lang(call.from_user.id)

    dino = await dinosaurs.find_one({'alt_id': alt_key})
    if dino:
        if action == 'start':
            if dino['status'] == 'pass':
                all_h, end = await check_hours(userid)
                h = await hours_now(userid)

                if h != 6 and all_h:
                    options = {}

                    if 6 - h != 0:
                        options[f"1 {t('time_format.hour.0', lang)}"] = 1
                    if 6 - h >= 3:
                        options[f"3 {t('time_format.hour.1', lang)}"] = 3
                    if 6 - h == 6:
                        options[f"6 {t('time_format.hour.2', lang)}"] = 6

                    bb = list_to_keyboard([
                        list(options.keys()), [t('buttons_name.cancel', lang)]
                    ], 2)

                    await ChooseOptionState(start_kind, userid, chatid, lang, options,
                                            transmitted_data={'dino': dino['_id']}
                                            )
                    await send_message(userid, t('kindergarten.choose_house', lang),
                                           reply_markup=bb)
                else:
                    await send_message(userid, t('kindergarten.no_hours', lang))
            else:
                await send_message(userid, t('alredy_busy', lang))

        elif action == 'stop':
            if dino['status'] == 'kindergarten':
                await dinosaurs.update_one({'_id': dino}, 
                         {'$set': {'status': 'pass'}})
                await send_message(userid, t('kindergarten.stop', lang))

async def start_kind(col, transmitted_data):
    chatid = transmitted_data['chatid']
    userid = transmitted_data['userid']
    lang = transmitted_data['lang']
    dino = transmitted_data['dino']

    await minus_hours(userid, col)
    await dinosaurs.update_one({'_id': dino}, 
                         {'$set': {'status': 'kindergarten'}})
    await dino_kind(dino, col)
    await send_message(chatid, t('kindergarten.ok', lang), 
                           reply_markup= await m(userid, 'last_menu', lang))