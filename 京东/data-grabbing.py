import time
import re
import requests
from pyquery import PyQuery as pq
from lxml import etree
import pymongo
import eventlet
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC



eventlet.monkey_patch()

MONGO_URL = 'localhost'
MONGO_DB = 'jingdong'
MONGO_TABLE = 'product'

client = pymongo.MongoClient(MONGO_URL)
db = client[MONGO_DB]

browser = webdriver.Chrome()
wait = WebDriverWait(browser, 10)
href_list = []  #保存详情页url



def search():
    '''
    搜索
    :return: 总页数
    '''
    try:
        browser.get('https://www.jd.com/')
        input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#key')))  #输入框
        input.send_keys('连衣裙')
        submit = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '#search > div > div.form > button')))  #搜索框
        submit.send_keys(Keys.ENTER)
        total = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#J_bottomPage > span.p-skip > em:nth-child(1) > b')))  #获取总页数
        get_url()
        return total.text
    except TimeoutException:
        return search()


def next_page():
    '''
    翻页
    :return:
    '''
    try:
        submit = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '#J_bottomPage > span.p-num > a.pn-next')))  #下一页
        submit.send_keys(Keys.ENTER)
        get_url()
    except TimeoutException:
        return next_page()


def get_url():
    '''
    获取详情页url
    :return:
    '''
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#J_goodsList .gl-item')))
        html = browser.page_source
        doc = pq(html)  #解析网页
        items = doc('#J_goodsList .gl-item').items()
        for item in items:
            href = re.compile('<div class="p-img".*?<a.*?href="(.*?)" onclick.*?</a>', re.S).search(str(item)).group(1)  #获取详情页url
            if 10 < len(href) < 50:  #滤过异常url
                # print(href)
                href_list.append(href)
    except TimeoutException:
        return get_url()


def get_products(href):
    '''
    获取产品信息
    :param href: 详情页url
    :return:
    '''
    try:
        href = 'http:' + href  # 构造url

        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.75 Safari/537.36'}
        response = requests.get(href, headers=headers, timeout=10)
        Selector = etree.HTML(response.text)

        browser.get(href)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'body')))
        html = browser.page_source
        doc = pq(html)
        print(href)
        datas = {
            '店铺名称': Selector.xpath('//*[@id="popbox"]/div/div[1]/h3/a/text()')[0],
            '店铺星级': re.compile('<div class="star".*?title="(.*?)".*?</div>', re.S).search(str(doc)).group(1),
            '商品评价': Selector.xpath('//*[@id="popbox"]/div/div[2]/div/a/div[2]/div[1]/span[2]/em/text()')[0],
            '物流履约': Selector.xpath('//*[@id="popbox"]/div/div[2]/div/a/div[2]/div[2]/span[2]/em/text()')[0],
            '售后服务': Selector.xpath('//*[@id="popbox"]/div/div[2]/div/a/div[2]/div[3]/span[2]/em/text()')[0],
            '商品编号': Selector.xpath('//*[@id="detail"]/div[2]/div[1]/div[1]/ul[2]/li[2]/@title')[0],
            '商品名称': Selector.xpath('//*[@id="detail"]/div[2]/div[1]/div[1]/ul[2]/li[1]/@title')[0],
            '价格': re.compile('<span class="p-price".*?<span class=.*?>(.*?)</span>', re.S).search(str(doc)).group(1),
            '粉丝价': re.compile('<span class="p-price-fans".*?<span class="price.*?>￥(.*?)</span>', re.S).search(
                str(doc)).group(1),
            '优惠券': re.compile('<span class="quan-item".*?<span class="text">(.*?)</span>', re.S).findall(str(doc)),
            '商品评价数': re.compile('div class="tab-main large.*?<s>\((.*?)\)</s>.*?</li>', re.S).search(str(doc)).group(1),
            '风格': Selector.xpath('//*[@id="detail"]/div[2]/div[1]/div[1]/ul[2]/li[7]/@title')[0],
            '领型': Selector.xpath('//*[@id="detail"]/div[2]/div[1]/div[1]/ul[2]/li[8]/@title')[0],
            '图案': Selector.xpath('//*[@id="detail"]/div[2]/div[1]/div[1]/ul[2]/li[10]/@title')[0],
            '裙型': Selector.xpath('//*[@id="detail"]/div[2]/div[1]/div[1]/ul[2]/li[12]/@title')[0],
            '流行元素': Selector.xpath('//*[@id="detail"]/div[2]/div[1]/div[1]/ul[2]/li[15]/@title')[0],
            '面料': Selector.xpath('//*[@id="detail"]/div[2]/div[1]/div[1]/ul[2]/li[16]/@title')[0],
            '裙长': Selector.xpath('//*[@id="detail"]/div[2]/div[1]/div[1]/ul[2]/li[19]/@title')[0]
        }
        # print(datas)
        save_to_mongo(datas)
    except TimeoutException:
        print('解析超时...')
    except Exception:  #异常处理(特殊网页不能提取)
        print('提取不成功!')


def save_to_mongo(result):
    '''
    数据保存
    :param result: 产品数据
    :return:
    '''
    try:
        if db[MONGO_TABLE].insert_one(result):
            print('successful!', result)
    except Exception:
        print('failure!', result)


def main():
    try:
        total = search()
        total = int(re.compile('(\d+)').search(total).group(1))
        # print(total)
        for i in range(2, 3):
            next_page()
            time.sleep(3)  #控制爬取速度应对反爬
        for href in href_list:
            # print(len(href_list))
            with eventlet.Timeout(10, False):
                get_products(href)
    except Exception:
        print('出现异常...')
    finally:
        browser.close()


if __name__ == '__main__':
    main()
