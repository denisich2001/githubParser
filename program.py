import requests
from lxml import html
import re
import time
import schedule
import logging
import os.path
import datetime

def pause():
  logging.info('Пауза 60 секунд!')
  time.sleep(60)


#Получаем страницу со списком обновленных репозиториев
def requestData(tag_name, page_number, requests_number, attempt=1):
  headers1 = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'}
  url = 'https://github.com/search?o=desc&p=%d&q=%s&s=updated&type=Repositories'%(page_number,tag_name)

  response = requests.get(url, headers = headers1)

  #Проверяем успешность передачи запроса
  if response.status_code == 200:
    logging.info("Успешный запрос!")
  elif response.status_code == 429:
    if attempt == 1:
      logging.warning("Error 429: Превышен лимит на количество запросов в минуту! Делаем паузу и повторяем запрос")
      pause()
      return requestData(tag_name, page_number, requests_number, 2)
    else:
      logging.error("Error 429: Повторное превышение лимита!")
  elif response.status_code == 404:
    logging.error("Error 404: Запрашиваемой страницы не существует! Url-запрос: " + url)
  else:
    logging.error("Error " + str(response.status_code)+": неизвестная ошибка при обращении к ресурсу!")

  return response


#Достаем все данные по тегу
def parseData(html_response):
  tree = html.fromstring(html_response)

  #Достаем ссылки на репозитории
  template_href = re.compile('\"url\":\"[^}]+\"')
  line_with_refs = tree.xpath('.//ul[@class = "repo-list"]//li//div[@class = "mt-n1 flex-auto"]//div[@class = "d-flex"]//a/@data-hydro-click').__str__()
  references = re.findall(template_href, line_with_refs)
  for i in range(len(references)):
    references[i] = references[i][7:-1]

  #Достаем название репозиториев
  names = list()
  for ref in references:
    names.append(re.search(r'.com/.+',ref)[0][5:])

  #Достаем дату обновления репозиториев
  dates = tree.xpath('.//ul[@class = "repo-list"]//li//div[@class = "mt-n1 flex-auto"]//div//div//div//relative-time/@datetime')

  data = list()
  for i in range(len(names)):
    data.append("Name: "+names[i]+"; Refference: "+references[i]+"; Date: "+dates[i][:10]+" "+dates[i][11:-1])

  return data

def get_old_posts():
  #Проверяем существование файла old_posts.txt
  old_posts = set()
  if os.path.exists('old_posts.txt'):
    #Файл существует, достаем последние сохраненные посты
    with open('old_posts.txt','r') as old_posts_file:
      while True:
        old_post = old_posts_file.readline()[:-1]
        if not old_post:
          break
        old_posts.add(old_post)
  else:
    #Создаем файл, т.к. он не был создан до этого
    with open('old_posts.txt','w') as old_posts_file:
      old_posts_file.write('')
  return old_posts


def get_tags():
  #Проверяем существование файла tags_list.txt
  tags_list = list()
  if os.path.exists('tags_list.txt'):
    tags = list()
    #Файл существует, получаем последние сохраненные посты
    with open('tags_list.txt', 'r') as tags_file:
      while True:
        tags_line = tags_file.readline()
        if not tags_line:
          break
        tags = list(tags_line.split('; '))

    if len(tags)>0 and tags[len(tags)-1][-1] == '\n':
      tags[len(tags)-1] = tags[len(tags)-1][:-1]
    return tags
  else:
    #Создаем файл, т.к. он не был создан до этого
    with open('tags_list.txt','w') as tags_file:
      tags_file.write('')

    return None


def main():
  print(str(datetime.datetime.now()))
  print("Скрипт запустился!")

  #Настраиваем логгирование
  logging.basicConfig (filename='logs.log', level = logging.INFO, format = '%(asctime)s  %(levelname)s: %(message)s', filemode = 'w', datefmt = '%d-%b-%y %H:%M:%S')
  logging.info("\n\nСкрипт начал свою работу!")

  #Получаем список тэгов для проверки
  tags = get_tags()
  if tags == None or len(tags)==0:
    print('Файл tags_list.txt пустой. Добавьте туда нужные тэгов через точку с запятой. Пример: python; parser; program')
    logging.error('Файл tags_list.txt пустой. Добавьте туда нужные тэгов через точку с запятой. Пример: python; parser; program')
    logging.info('Работа скрипта была завершена с ошибкой!')
    return

  logging.info('Тэги для проверки: ' + str(tags))

  #Получаем список старых постов, чтобы выводить только новые
  old_posts = get_old_posts()
  if len(old_posts)==0:
    logging.info('Сохраненных старых постов нет!')
  else:
    logging.info('Сохраненные старые посты получены. Количество: '+str(len(old_posts)))
  requests_number = 0 #Общее число запросов
  new_posts = list() #Список новых постов

  new_posts_number = 0
  for tag in tags:
    print("-----------------------------------------\n")
    print("Проверяем тэг "+tag)
    #Ждем на минуту на каждом девятом запросе, чтобы избежать Error 429
    if requests_number % 9 ==0:
      pause()

    logging.info("\n\nТекущий тэг: " + tag)

    page_number = 1
    stop_parsing = False
    tag_new_posts_number = 0
    while not stop_parsing:
      requests_number += 1
      logging.info("Запрос " + str(page_number) + " страницы со списком результатов по текущему тэгу")
      response = requestData(tag, page_number, requests_number)
      if response.status_code != 200:
        logging.warning("Ошибка запроса. Переходим к следующему тэгу!")
        break

      #Достаем данные из запроса
      posts = parseData(response.text)

      #Проверяем нет ли среди новых постов - уже рассматриваемых
      for post in posts:
        if post in old_posts:
          #Останавливаемся, т.к. этот пост - уже рассматривали
          print("Рассматривали")
          new_posts.append(post)
          stop_parsing = True
          break
        new_posts_number = new_posts_number + 1
        tag_new_posts_number = tag_new_posts_number + 1
        print("Новый пост к тэгу "+tag+":\n" + post)
        new_posts.append(post)

      page_number += 1
      if new_posts_number == 0 or new_posts_number % 10 != 0:
        stop_parsing = True
      #Ограничили количество новых постов тридцатью
      if requests_number % 3 == 0:
        stop_parsing = True

    print("Количество новых постов для текущего тэга",tag_new_posts_number)
    logging.info("Количество новых постов для текцщего тэга: "+str(tag_new_posts_number))


  logging.info("Количество новых постов записанных в файл: "+str(new_posts_number))
  with open('old_posts.txt', 'a+') as old_posts_file:
    if len(new_posts) != 0:
      old_posts_file.write('\n'.join(new_posts))

  print("Скрипт закончил работу!")


if __name__ == "__main__":
  schedule.every().day.at("09:00:00").do(main)
  while True:
    schedule.run_pending()
    time.sleep(1)
