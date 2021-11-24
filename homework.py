import logging
import os
import time
from http import HTTPStatus
import requests
import telegram
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


class AnswerAPIError(Exception):
    """Ошибка при сбое в работе API."""

    pass


def send_message(bot, message):
    """Функция send_message отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logging.info('Удачная отправка сообщения в Telegram')
    except Exception as error:
        logging.error(f'Сбой при отправке сообщения, ошибка {error}')


def get_api_answer(current_timestamp):
    """Функция get_api_answer делает запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, params=params, headers=HEADERS)
        if response.status_code != HTTPStatus.OK:
            raise Exception('Эндпоинт не отвечает')
        return response.json()
    except Exception:
        raise AnswerAPIError('Сбои в работе API')


def check_response(response):
    """Функция check_response проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не словарь')
    if ['homeworks'][0] not in response:
        raise IndexError('В ответе API нет домашней работы')
    homework = response.get('homeworks')[0]
    return homework


def parse_status(homework):
    """Функция parse_status извлекает статус конкретной домашней работы."""
    keys = ['homework_name', 'status']
    for key in keys:
        if key not in homework:
            raise KeyError(f'Ожидаемый ключ {key} отсутствует в ответе API')
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        raise KeyError('Неизвестный статус домашней работы')
    homework_name = homework['homework_name']
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Функция check_tokens проверяет доступность переменных окружения."""
    variables = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    result = True
    for variable in variables:
        if variable is None:
            result = False
        return result


def main():
    """Основная логика работы бота."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s, %(levelname)s, %(message)s',
        handler=[logging.StreamHandler()]
    )

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    logger = logging.getLogger(__name__)

    while True:
        try:
            check_tokens()
            response = get_api_answer(current_timestamp)
            if 'current_date' in response:
                current_timestamp = response['current_date']
            if 'homeworks' in response:
                checked_response = check_response(response)
                message = parse_status(checked_response)
                if message is not None:
                    send_message(bot, message)
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
