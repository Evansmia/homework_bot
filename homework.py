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

STATUS_ERROR = 'Статус {status} не установлен.'
ANSWER_ERROR = ('code={code}\n'
                'error={error}\n')
UNEXPECTED_STATUS = ('status={status}\n')


class AnswerAPIError(Exception):
    """Ошибка при сбое в работе API."""

    pass


class CheckResponseError(Exception):
    """Ошибка при получении пустого списка."""

    pass


class UnexpectedStatusError(Exception):
    """Неожидаемый статус запроса к эндпоинту."""

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
    except requests.exceptions.RequestException as error:
        message = (f'Ошибка соединения {error}')
        logging.critical(message)
    if response.status_code == HTTPStatus.OK:
        response = response.json()
        keys = ['code', 'error']
        for error in keys:
            if error in response:
                raise AnswerAPIError(ANSWER_ERROR.format(
                    code=response['code'],
                    error=response['error']))
        return response
    raise UnexpectedStatusError(
        UNEXPECTED_STATUS.format(status=response.status_code))


def check_response(response):
    """Функция check_response проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не словарь')
    if response.get('homeworks') is None:
        raise KeyError
    if response['homeworks']:
        return response.get('homeworks')[0]
    raise CheckResponseError('Список homeworks пустой')


def parse_status(homework):
    """Функция parse_status извлекает статус конкретной домашней работы."""
    keys = ['homework_name', 'status']
    for key in keys:
        if key not in homework:
            raise KeyError(f'Ожидаемый ключ {key} отсутствует в ответе API')
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        raise ValueError(STATUS_ERROR.format(status=homework_status))
    homework_name = homework['homework_name']
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Функция check_tokens проверяет доступность переменных окружения."""
    variables = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    for variable in variables:
        if variable is None:
            return False
        return True


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
            current_timestamp = response['current_date']
            checked_response = check_response(response)
            message = parse_status(checked_response)
            previous_message = None
            if previous_message != message:
                send_message(bot, message)
                previous_message = message
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
