import telebot
from telebot import types
import config
import random
import json
import pymongo
from PIL import Image, ImageFont, ImageDraw, ImageOps, ImageSequence, ImageFilter
import io
from io import BytesIO
from functions import functions
import time
import os
import threading

bot = telebot.TeleBot(config.TOKEN)

client = pymongo.MongoClient(config.CLUSTER_TOKEN)
users = client.bot.users

def user_dino_pn(user):
    if len(user['dinos'].keys()) == 0:
        return '1'
    else:
        id_list = []
        for i in user['dinos'].keys():
            try:
                id_list.append(int(i))
            except:
                pass
        return str(max(id_list))

def random_dino(user, dino_id_remove):
    dino_id = random.choice(json_f['data']['dino'])
    dino = json_f['elements'][str(dino_id)]
    del user['dinos'][dino_id_remove]
    user['dinos'][user_dino_pn(user)] = {"status": 'dino_child', 'name': None, 'stats':  {"heal": 100, "eat": 100, 'game': 100, 'mood': 100, "unv": 100}}

    users.update_one( {"userid": user['userid']}, {"$set": {'dinos': user['dinos']}} )


def notifications_manager(notification, user, arg = None):
    if user['settings']['notifications'] == True:
        chat = bot.get_chat(user['userid'])

        if notification == "5_min_incub":

            if user['language_code'] == 'ru':
                text = f'🥚 | {chat.first_name}, ваш динозавр вылупится через 5 минут!'
            else:
                text = f'🥚 | {chat.first_name}, your dinosaur will hatch in 5 minutes!'

            bot.send_message(user['userid'], text)

        if notification == "incub":

            if user['language_code'] == 'ru':
                text = f'🦖 | {chat.first_name}, динозавр вылупился!!'
            else:
                text = f'🦖 | {chat.first_name}, the dinosaur has hatched!!'

            bot.send_message(user['userid'], text)

def check(): #проверка каждые 10 секунд
    while True:
        time.sleep(5)

        members = users.find({ })
        for user in members:

            for dino_id in user['dinos'].keys():
                dino = user['dinos'][dino_id]
                if dino['status'] == 'incubation': #инкубация
                    if dino['incubation_time'] - int(time.time()) <= 60*5 and dino['incubation_time'] - int(time.time()) > 0: #уведомление за 5 минут

                        if 'inc_notification' in list(user['notifications'].keys()):

                            if user['notifications']['inc_notification'] == False:
                                notifications_manager("5_min_incub", user, dino)

                                user['notifications']['inc_notification'] = True
                                users.update_one( {"userid": user['userid']}, {"$set": {'notifications': user['notifications']}} )

                        else:
                            user['notifications']['inc_notification'] = True
                            users.update_one( {"userid": user['userid']}, {"$set": {'notifications': user['notifications']}} )

                            notifications_manager("5_min_incub", user, dino_id)


                    elif dino['incubation_time'] - int(time.time()) <= 0:

                        if 'inc_notification' in list(user['notifications'].keys()):
                            del user['notifications']['inc_notification']
                            users.update_one( {"userid": user['userid']}, {"$set": {'notifications': user['notifications']}} )

                        random_dino(user, dino_id)
                        notifications_manager("incub", user, dino_id)
                        break


thr1 = threading.Thread(target = check, daemon=True)


with open('../images/dino_data.json') as f:
    json_f = json.load(f)

def markup(element = 1, user = None):
    markup = types.ReplyKeyboardMarkup(resize_keyboard = True)

    if element == 1 and users.find_one({"userid": user.id}) != None:

        if user.language_code == 'ru':
            nl = ['🦖 Динозавр', '🎢 Рейтинг']
        else:
            nl = ['🦖 Dinosaur', '🎢 Rating']

        item1 = types.KeyboardButton(nl[0])
        item2 = types.KeyboardButton(nl[1])

        markup.add(item1, item2)

    elif element == 1:
        if user.language_code == 'ru':
            nl = ['🍡 Начать играть']
        else:
            nl = ['🍡 Start playing']

        item1 = types.KeyboardButton(nl[0])

        markup.add(item1)


    return markup


@bot.message_handler(commands=['start', 'help'])
def on_start(message):
    user = message.from_user
    if users.find_one({"userid": user.id}) == None:
        if user.language_code == 'ru':
            text = f"🎋 | Хей <b>{user.first_name}</b>, рад приветствовать тебя!\n"+ f"<b>•</b> Я маленький игровой бот по типу тамагочи, только с динозаврами!🦖\n\n"+f"<b>🕹 | Что такое тамагочи?</b>\n"+f'<b>•</b> Тамагочи - игра с виртуальным питомцем, которого надо кормить, ухаживать за ним, играть и тд.🥚\n'+f"<b>•</b> Соревнуйтесь в рейтинге и станьте лучшим!\n\n"+f"<b>🎮 | Как начать играть?</b>\n"+f'<b>•</b> Нажмите кномку <b>🍡 Начать играть</b>!\n\n'+f'<b>❤ | Ждём в игре!</b>\n'
        else:
            text = f"🎋 | Hey <b>{user.first_name}</b>, I am glad to welcome you!\n" +f"<b>•</b> I'm a small tamagotchi-type game bot, only with dinosaurs!🦖\n\n"+f"<b>🕹 | What is tamagotchi?</b>\n"+ f'<b>•</b> Tamagotchi is a game with a virtual pet that needs to be fed, cared for, played, and so on.🥚\n'+ f"<b>•</b> Compete in the ranking and become the best!\n\n"+ f"<b>🎮 | How to start playing?</b>\n" + f'<b>•</b> Press the button <b>🍡Start playing</b>!\n\n' + f'<b>❤ | Waiting in the game!</b>\n' +f'<b>❗ | In some places, the bot may not be translated!</b>\n'

        bot.reply_to(message, text, reply_markup = markup(user = user), parse_mode = 'html')
    else:
        bot.reply_to(message, '👋', reply_markup = markup(user = user), parse_mode = 'html')


@bot.message_handler(content_types = ['text'])
def on_message(message):
    user = message.from_user

    def trans_paste(fg_img,bg_img,alpha=10,box=(0,0)):
        fg_img_trans = Image.new("RGBA",fg_img.size)
        fg_img_trans = Image.blend(fg_img_trans,fg_img,alpha)
        bg_img.paste(fg_img_trans,box,fg_img_trans)
        return bg_img

    if message.chat.type == 'private':

        if message.text in ['🍡 Начать играть', '🍡 Start playing']:
            if users.find_one({"userid": user.id}) == None:

                def photo():
                    global json_f
                    bg_p = Image.open(f"../images/remain/{random.choice(['back', 'back2'])}.png")
                    eg_l = []
                    id_l = []

                    for i in range(3):
                        rid = str(random.choice(list(json_f['data']['egg'])))
                        image = Image.open('../images/'+str(json_f['elements'][rid]['image']))
                        eg_l.append(image)
                        id_l.append(rid)

                    for i in range(3):
                        bg_img = bg_p
                        fg_img = eg_l[i]
                        img = trans_paste(fg_img, bg_img, 1.0, (i*512,0))

                    img.save('eggs.png')
                    photo = open(f"eggs.png", 'rb')

                    return photo, id_l

                if user.language_code == 'ru':
                    text = '🥚 | Выберите яйцо с динозавром!'
                else:
                    text = '🥚 | Choose a dinosaur egg!'

                users.insert_one({'userid': user.id, 'dinos': {}, 'eggs': [], 'notifications': {}, 'settings': {'notifications': True}, 'language_code': user.language_code})

                markup_inline = types.InlineKeyboardMarkup()
                item_1 = types.InlineKeyboardButton( text = '🥚 1', callback_data = 'egg_answer_1')
                item_2 = types.InlineKeyboardButton( text = '🥚 2', callback_data = 'egg_answer_2')
                item_3 = types.InlineKeyboardButton( text = '🥚 3', callback_data = 'egg_answer_3')
                markup_inline.add(item_1, item_2, item_3)

                photo, id_l = photo()
                bot.send_photo(message.chat.id, photo, text, reply_markup = markup_inline)
                users.update_one( {"userid": user.id}, {"$set": {'eggs': id_l}} )
                try:
                    os.remove('eggs.png')
                except Exception:
                    pass

    if message.text in ['🦖 Динозавр', '🦖 Dinosaur']:
        bd_user = users.find_one({"userid": user.id})
        if bd_user != None:

            def egg_profile(bd_user, user):
                egg_id = bd_user['dinos'][ list(bd_user['dinos'].keys())[0] ]['egg_id']
                lang = user.language_code
                time = int(t_incub)
                time_end = functions.time_end(time, True)

                bg_p = Image.open(f"../images/remain/egg_profile_{lang}.png")
                egg = Image.open("../images/"+str(json_f['elements'][egg_id]['image']))

                bg_img = bg_p
                fg_img = egg
                img = trans_paste(fg_img, bg_img, 1.0, (-95,-50))

                idraw = ImageDraw.Draw(img)
                line1 = ImageFont.truetype("../fonts/FloraC.ttf", size = 35)

                idraw.text((390,100), time_end, font = line1)

                img.save('profile.png')
                profile = open(f"profile.png", 'rb')
                return profile

            if len(bd_user['dinos'].keys()) == 0:
                pass

            elif len(bd_user['dinos'].keys()) == 1:
                if bd_user['dinos'][ list(bd_user['dinos'].keys())[0] ]['status'] == 'incubation':

                    t_incub = bd_user['dinos'][ list(bd_user['dinos'].keys())[0] ]['incubation_time'] - time.time()
                    if t_incub < 0:
                        t_incub = 0
                    profile = egg_profile(bd_user, user)
                    bot.send_photo(message.chat.id, profile)

                    try:
                        os.remove('profile.png')
                    except Exception:
                        pass
            else:
                pass


@bot.callback_query_handler(func = lambda call: True)
def answer(call):

    if call.data in ['egg_answer_1', 'egg_answer_2', 'egg_answer_3']:
        user = call.from_user
        bd_user = users.find_one({"userid": user.id})

        if 'eggs' in list(bd_user.keys()):
            egg_n = call.data[11:]

            bd_user['dinos'][ user_dino_pn(bd_user) ] = {'status': 'incubation', 'incubation_time': time.time() + 60 * 30, 'egg_id': bd_user['eggs'][int(egg_n)-1]}

            users.update_one( {"userid": user.id}, {"$unset": {'eggs': 1}} )
            users.update_one( {"userid": user.id}, {"$set": {'dinos': bd_user['dinos']}} )

            if user.language_code == 'ru':
                text = f'🥚 | Выберите яйцо с динозавром!\n🦖 | Вы выбрали яйцо 🥚{egg_n}!'
                text2 = f'Поздравляем, у вас появился свой первый динозавр!\nВ данный момент яйцо инкубируется, а через 30 минут из него вылупится динозаврик!\nЧтобы посмотреть актуальную информацию о яйце, нажмите кнопку <b>🦖 Динозавр</b>!'
            else:
                text = f'🥚 | Choose a dinosaur egg!\n🦖 | You have chosen an egg 🥚{egg_n}!'
                text2 = f'Congratulations, you have your first dinosaur!\n At the moment the egg is incubating, and after 12 hours a dinosaur will hatch out of it!To view up-to-date information about the egg, click <b>🦖 Dinosaur</b>!'

            bot.edit_message_caption(text, call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, text2, parse_mode = 'html', reply_markup = markup(1, user))



print(f'Бот {bot.get_me().first_name} запущен!')
thr1.start()

bot.infinity_polling(none_stop = True)
