from urllib.parse import quote

from bs4 import BeautifulSoup
from utils import requests


class SpecCategory:
    def __init__(self, section):
        self.name = section.find('tr th').get_text()


class Specs:
    def __init__(self, page_data):
        pass


class PhoneModel:
    def __init__(self, name, relative_url):
        self.name = name
        self.url = 'https://gsmarena.com/' + relative_url
        self.specs = None

    async def fetch_specs(self):
        if self.specs is not None:
            return self.specs

        page = await requests.get(self.url)
        body = page.decode()
        soup = BeautifulSoup(body, 'html.parser')
        spec_list = soup.find(id='specs-list')
        spec_sections = spec_list.find_all('table')

        return 'oh no, our ip, it\'s banned'

        #return spec_sections
        #return [SpecCategory(section) for section in spec_sections]


async def search_phones(query: str):
    page = await requests.get('https://gsmarena.com/res.php3?sSearch=' + quote(query))
    body = page.decode()
    soup = BeautifulSoup(body, 'html.parser')
    makers = soup.find(class_='makers')

    if not makers:
        return None

    phones = makers.find_all('a')
    return [PhoneModel(phone.get_text(' '), phone.get('href')) for phone in phones]
