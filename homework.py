import http
import logging
from logging.handlers import RotatingFileHandler
import os
import time

import requests
from telebot import TeleBot
from dotenv import load_dotenv

from exceptions import CriticalError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    valid = True
    tokens = {
        "PRACTICUM_TOKEN": PRACTICUM_TOKEN,
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID
    }
    for name, token in tokens.items():
        if not token:
            valid = False
            logging.error(f'Токен {name} недоступен')
    return valid


def send_message(bot, message):
    """Отправляет сообщение со статусом работы в Telegram-чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug('Сообщение отправлено!')
    except Exception:
        raise requests.RequestException('Сообщение не отправлено!')


def get_api_answer(timestamp):
    """Делает запрос к API и возвращает ответ при успешном запросе."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
    except requests.RequestException as req_err:
        # Тест ругается на внешние исключения, проходит только
        # с встроенными
        raise ConnectionError(f'Возникла проблема: {req_err}')
    if response.status_code != http.HTTPStatus.OK:
        raise requests.RequestException(
            'Отсутствует доступ к эндпоинту'
        )
    return response.json()


def check_response(response):
    """Проверяет правильно полученный API ответ."""
    if not isinstance(response, dict):
        raise TypeError(
            f'Тип переменной "response": ожидался dict, '
            f'получен {type(response)}'
        )
    if 'homeworks' not in response:
        raise KeyError(
            'Отсутствует ключ "homeworks" в полученном ответе'
        )

    if not isinstance(response['homeworks'], list):
        raise TypeError(
            f'Тип переменной "homeworks": ожидался list, '
            f'получен {type(response["homeworks"])}')


def parse_status(homework):
    """Извлекает из информации статус домашней работы."""
    for key in ('homework_name', 'status'):
        if key not in homework:
            raise KeyError(
                f'{key} отсутствует в списке '
                'домашних работ "homework"'
            )
    if homework['status'] == 'unknown':
        raise KeyError('Статус работы "unknown"')
    homework_name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise KeyError('Статус работы отсутствует')
    verdict = HOMEWORK_VERDICTS[status]
    return (
        f'Изменился статус проверки работы '
        f'"{homework_name}". {verdict}'
    )


def main():
    """Основная логика работы бота."""
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp, last_message, last_error_message = 0, '', ''
    if not check_tokens():
        crit_message = 'Отсутствуют необходимые токены'
        logging.critical(crit_message)
        raise CriticalError(crit_message)
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homework = response.get('homeworks')
            timestamp = response.get('current_date')
            message = parse_status(homework[0])
            if last_message != message:
                send_message(bot, message)
                last_message = message
            else:
                logging.debug('Новый статус отсутствует')
            if not homework:
                logging.debug('Список домашних работ пуст')
        except Exception as error:
            error_message = f'Сбой в работе программы: {error}'
            logging.error(error_message)
            if last_error_message != error_message:
                send_message(bot, error_message)
                last_error_message = error_message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    # Забыл в прошлый раз оставить комментарий про кастомный логгер
    # Тесты не проходили внутри if __name__ == '__main__'
    # Через basicConfig все нормально почему-то :)
    terminal_handler = logging.StreamHandler()
    file_handler = RotatingFileHandler(
        'main.log', maxBytes=5 * 1024 * 1024, backupCount=5
    )
    formatter = logging.Formatter(
        '%(asctime)s, %(levelname)s, %(name)s, '
        'строка: %(lineno)d, функция: %(funcName)s, %(message)s'
    )
    file_handler.setFormatter(formatter)
    terminal_handler.setFormatter(formatter)

    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[file_handler, terminal_handler],
    )
    main()
