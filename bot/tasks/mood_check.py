from time import time

from bot.config import conf, mongo_client
from bot.modules.dinosaur import mutate_dino_stat
from bot.taskmanager import add_task
from bot.modules.logs import log

dino_mood = mongo_client.dinosaur.dino_mood
dinosaurs = mongo_client.dinosaur.dinosaurs

REPEAT_MINUTES = 5

async def mood_check():
    """ Проверяет и выдаёт настроение
    """
    res = list(await dino_mood.find({}).to_list(None)) 
    upd_data = {}

    for mood_data in res:
        try:
            dino_id = mood_data['dino_id']

            if mood_data['type'] in ['mood_edit', 'mood_while']:
                if dino_id in upd_data:
                    upd_data[dino_id]['unit'] += mood_data['unit']
                else: upd_data[dino_id] = {'unit': mood_data['unit'], 
                                        'while': [], 'events': []
                                        }

            if mood_data['type'] == 'mood_edit':
                if int(time()) >= mood_data['end_time']:
                    # Закончилось время эффекта
                    await dino_mood.delete_one({'_id': mood_data['_id']})

            elif mood_data['type'] == 'mood_while':
                while_data = mood_data['while']
                while_data['_id'] = mood_data['_id']

                upd_data[dino_id]['while'].append(while_data)

            if mood_data['type'] in ['breakdown', 'inspiration']:
                if dino_id not in upd_data: upd_data[dino_id] = {
                    'unit': 0, 'events': []
                    }
                upd_data[dino_id]['events'].append(
                    {'_id': mood_data['_id'], 
                    'cancel_mood': mood_data['cancel_mood'],
                    'type': mood_data['type']
                    }
                )

                if int(time()) >= mood_data['end_time']:
                    # Закончилось время эффекта
                    await dino_mood.delete_one({'_id': mood_data['_id']})

                    if mood_data['action'] == 'hysteria':
                        await dinosaurs.update_one({'_id': dino_id}, 
                                            {'$set': {'status': 'pass'}})
        except Exception as e:
            log(f'mood_data error {e}, {mood_data}')

    for dino_id, data in upd_data.items():
        try:
            dino = await dinosaurs.find_one({'_id': dino_id})

            if dino:
                if data['unit'] != 0:
                    await mutate_dino_stat(dino, 'mood', data['unit'])

                for while_data in data['while']:
                    char = while_data['characteristic']
                    if while_data['min_unit'] >= dino['stats'][char] or \
                        dino['stats'][char] >= while_data['max_unit']:
                            await dino_mood.delete_one({'_id': while_data['_id']})

                for event_data in data['events']:
                    if event_data['type'] == 'breakdown':
                        if dino['stats']['mood'] >= event_data['cancel_mood']:
                            await dino_mood.delete_one({'_id': event_data['_id']})

                            if upd_data['action'] == 'hysteria':
                                await dinosaurs.update_one({'_id': dino_id}, 
                                                    {'$set': {'status': 'pass'}})

                    if event_data['type'] == 'inspiration':
                        if dino['stats']['mood'] <= event_data['cancel_mood']:
                            await dino_mood.delete_one({'_id': event_data['_id']})
            else: await dino_mood.delete_many({'dino_id': dino_id})
        except Exception as e:
            log(f'upd_data error {e}, {data} {dino_id}')


async def break_down():
    res = list(await dinosaurs.find({'status': 'hysteria'}).to_list(None))

    for i in res:
        dino_id = i['_id']
        res_s = await dino_mood.find_one({'dino_id': dino_id, 'action': 'hysteria'})

        if not res_s:
            await dinosaurs.update_one({'_id': dino_id}, {'$set': {'status': 'pass'}})

if __name__ != '__main__':
    if conf.active_tasks:
        add_task(mood_check, REPEAT_MINUTES * 60.0, 5.0)
        add_task(break_down, REPEAT_MINUTES * 60.0, 10.0)