from datetime import datetime, timezone
from random import choice, randint, choices
from time import time

from bot.config import conf, mongo_client
from bot.exec import bot
from bot.modules.data_format import seconds_to_str
from bot.modules.localization import get_data, t
from bot.modules.notifications import user_notification
from bot.modules.quests import create_quest, quest_resampling, save_quest
from bot.taskmanager import add_task
from bot.modules.over_functions import send_message

users = mongo_client.user.users
tavern = mongo_client.tavern.tavern
quests_data = mongo_client.tavern.quests
daily_data = mongo_client.tavern.daily_award

async def tavern_quest(user):
    free_quests = list(await quests_data.find(
        {'owner_id': 0}, {'_id': 1}).to_list(None))  
    lang = user['lang']

    if await quests_data.count_documents({'owner_id': user['userid']}) < 5:
        if free_quests and not randint(0, 3):
            ran_quest = choice(free_quests)
            free_quests.remove(ran_quest)

            quest_id = ran_quest['_id']

            new_time = ran_quest['time_end'] - ran_quest['time_start']
            await quests_data.update_one({'_id': quest_id}, {"$set": {
                'owner_id': user['userid'], 
                'time_start': int(time()), 
                'end_time': int(time()) + new_time}})

            text = t('quest.resаmpling', lang)
        else:
            compl = choices([2, 1], [0.25, 0.5])[0]

            quest = create_quest(compl, lang=lang)
            await save_quest(quest, user['userid'])
            text = t('quest.new', lang)

        try: await send_message(user['userid'], text)
        except: pass

async def tavern_replic(in_tavern, user):
    names = in_tavern.copy()
    names.remove(user)

    game_names = get_data('quests.authors', user['lang'])
    names += game_names

    if names:
        random_name = choice(names)
        if type(random_name) == dict:
            random_name = random_name['name']
        random_replic = choice(get_data('tavern_dialogs', user['lang']))

        text = f'👤 {random_name}: {random_replic}'
        try:
            await send_message(user['userid'], text)
        except Exception: pass

async def tavern_life():
    in_tavern = list(await tavern.find({}).to_list(None)) 

    for user in in_tavern:
        if user['time_in'] + 3600 <= int(time()):
            await tavern.delete_one({'_id': user['_id']})
            try:
                await send_message(user['userid'], 
                        t('tavern_sleep', user['lang']))
            except: pass

        elif randint(1, 10) == 5: await tavern_replic(in_tavern, user)
        elif randint(1, 10) == 5: await tavern_quest(user)

async def quest_managment():
    quests = await quests_data.find({}).to_list(None)  
    now = datetime.now(timezone.utc)

    for quest in quests:
        create = quest['_id'].generation_time
        delta = now - create

        if delta.seconds >= 2592000:
            await quests_data.delete_one({'_id': quest['_id']})

        elif int(time()) >= quest['time_end']:
            await quest_resampling(quest['_id'])

async def daily_award_old():
    data = await daily_data.find(
        {'time_end': {'$lte': int(time())}}).to_list(None)  
    for i in list(data): await daily_data.delete_one({'_id': i['_id']})

async def daily_award_notif():
    users_ids = await users.find({}, 
                        {'userid': 1, 'settings': 1}).to_list(None) 

    for uid in users_ids:
        if not daily_data.find_one({'owner_id': uid['userid']}):
            if uid['settings']['notifications']:
                await user_notification(uid['userid'], 'daily_award')

if __name__ != '__main__':
    if conf.active_tasks:
        add_task(daily_award_notif, 36000.0, 10800.0)
        add_task(daily_award_old, 7200.0, 1.0)
        add_task(tavern_life, 180.0, 10.0)
        add_task(quest_managment, 240.0, 10.0)