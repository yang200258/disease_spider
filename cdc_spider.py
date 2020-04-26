import uuid
from datetime import datetime
from urllib import parse
from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED

from scrapy import Selector
import requests

from cdc_models import t_article, t_category

unspider_title = ['烟草控制', '妇幼保健']
domain = 'http://www.chinacdc.cn/jkzt/'
domain_health = 'http://www.jkb.com.cn/healthyLiving/jkzs/'
health_urls = []
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.113 Safari/537.36'
}


def get_article_urls():
    # 请求健康主题页面
    res_text = requests.get(domain, headers=headers).text
    sel = Selector(text=res_text)
    # 获取所有主题url
    all_urls = sel.xpath("//ul[@class='sr-ul']/li/a/@href").extract()
    return all_urls


def get_health_urls(url):
    res_health = requests.get(url).content
    res_text = res_health.decode('utf-8', 'ignore').encode('utf-8', 'ignore')
    health_sel = Selector(text=res_text)
    urls = health_sel.xpath("//div[@class='mainL fl']/ul/li/div[@class='txt']/h4/a/@href").extract()
    for url in urls:
        health_urls.append(url)
    try:
        # 处理下一页逻辑
        next_page_url = health_sel.xpath("//ul[@class='pagination']/li/a/@href").extract()[-1]
        get_health_urls(next_page_url)
    except:
        print("获取健康知识url完成")
        return


def get_health_article(url):
    res_article = requests.get(url).content
    res_article = res_article.decode('utf-8', 'ignore').encode('utf-8', 'ignore')
    article_sel = Selector(text=res_article)
    title = article_sel.xpath("//div[@class='title']/h3/text()").extract()[0]
    title_item = article_sel.xpath("//div[@class='title']/*[@class='mainLH5']/span[@class='fl']/text()").extract()
    create_time = datetime.strptime(title_item[0].split(' ')[0], "%Y-%m-%d")
    source = article_sel.xpath("//div[@class='title']/*[@class='mainLH5']/span[@class='fl']/a/text()").extract()[0]
    content = article_sel.xpath("//div[@class='content']").extract()[0]
    save_article(title, create_time, '健康知识', content, url, source)


def get_topic(url):
    # 获取每个主题进入下一分类的url
    next_url = parse.urljoin(domain, url.strip())
    res_next_page = requests.get(next_url, headers=headers).text
    next_page_sel = Selector(text=res_next_page)
    # 根据下一分类标题判断是否为传染病主题
    if len(next_page_sel.xpath("//div[@class='cn-title']/p/text()").extract()) == 0:
        # 处理传染病逻辑
        # 保存一级分类
        save_category('传染病', '')
        # 获取传染病下二级分类子病的url
        crb_urls = next_page_sel.xpath(
            "//div[@class='spread-tab-cn tab-cn']//ul[@class='ji-result-ul']/li/a/@href").extract()
        for url in crb_urls:
            # 获取每个文章url及二级分类名称
            crb_article_url, crb_level2_category = levele2_disease(next_url, url)
            # 保存二级分类
            save_category(crb_level2_category, '传染病')
            # executor.submit(save_category, crb_level2_category, '传染病')
            # print(crb_level2_category, crb_article_url)
            # deal_article_page(crb_article_url, crb_level2_category)
            # 启动多线程 **********************
            task1 = executor.submit(deal_article_page, crb_article_url, crb_level2_category)
            wait([task1], return_when=ALL_COMPLETED)
    else:
        # 一级分类名称
        disease_category = next_page_sel.xpath("//div[@class='cn-title']/p/text()").extract()[0]
        # 保存一级分类
        save_category(disease_category, '')
        topic = next_page_sel.xpath("//h2[@class='method-item-title']/a/text()").extract()[0]
        if topic == '中毒有关知识':
            next_page_topic = next_page_sel.xpath("//h2[@class='method-item-title']/a/text()").extract()[1]
            next_page_url = next_page_sel.xpath("//h2[@class='method-item-title']/a/@href").extract()[1]
        else:
            next_page_topic = next_page_sel.xpath("//h2[@class='method-item-title']/a/text()").extract()[0]
            next_page_url = next_page_sel.xpath("//h2[@class='method-item-title']/a/@href").extract()[0]
        if disease_category not in unspider_title:
            if next_page_topic == '知识天地':
                # 处理不带有二级分类的文章
                article_url = parse.urljoin(next_url, next_page_url)
                # deal_article_page(article_url, disease_category)
                # 启动多线程 **********************
                task2 = executor.submit(deal_article_page, article_url, disease_category)
                wait([task2], return_when=ALL_COMPLETED)
            else:
                # 处理带二级分类的文章(突发事件+慢病)
                next_page_url = next_page_url.strip()
                level2_url_article = parse.urljoin(next_url, next_page_url)
                res_levele2_urls = requests.get(level2_url_article, headers=headers).text
                levele2_sel = Selector(text=res_levele2_urls)
                item_li = levele2_sel.xpath("//ul[@class='jal-item-list']/li")
                for li in item_li:
                    item_url = li.xpath(".//a/@href").extract()[0]
                    item_category = li.xpath(".//a/text()").extract()[0]
                    if next_page_topic != '职业病防治知识':
                        save_category(item_category, disease_category)
                        item_category = '职业卫生与中毒控制'
                    try:
                        # 获取每个文章url及二级分类名称
                        levele2_url, level2_category = levele2_disease(level2_url_article, item_url)
                        # 保存二级分类
                    except IndexError as e:
                        level3_url = parse.urljoin(level2_url_article, item_url, item_category)

                        # deal_article_page(level3_url, item_category)
                        # 启动多线程 **********************
                        task3 = executor.submit(deal_article_page, level3_url, item_category)
                        wait([task3])
                        continue
                    # deal_article_page(levele2_url, level2_category)
                    # 启动多线程 **********************
                    task4 = executor.submit(deal_article_page, levele2_url, level2_category)
                    wait([task4])
        else:
            return


def levele2_disease(previous_url, url):
    """
    处理二级分类页面
    :param previous_url:进入一级分类的url
    :param url:进入二级分类的url
    :return:
    """
    url = url.strip()
    levele2_url = parse.urljoin(previous_url, url)
    res_levele2_urls = requests.get(levele2_url, headers=headers).text
    levele2_sel = Selector(text=res_levele2_urls)
    # 获取二级分类名称
    levele2_title = levele2_sel.xpath("//div[@class='cn-title']/p/text()").extract()[0]
    # 获取二分类url
    levele2_url_kw = levele2_sel.xpath("//h2[@class='method-item-title']/a/@href").extract()[0]
    article_url = parse.urljoin(levele2_url, levele2_url_kw.strip())
    return article_url, levele2_title


def deal_article_page(article_url, category):
    """
    获取文章列表页面
    :param article_url: 文章页面的地址（知识天地url）
    :return:
    """
    res_article = requests.get(article_url, headers=headers).text
    article_sel = Selector(text=res_article)
    try:
        item_urls_top = article_sel.xpath("//div[@class='item-top-text']//a/@href").extract()[0]
        deal_article_content(article_url, item_urls_top, category)
        # 启动多线程 **********************
        # executor.submit(deal_article_content, article_url, item_urls_top, category)
    except:
        item_urls_top = None
    # 传染病处理获取每篇文章url方式
    item_urls_bottom1 = article_sel.xpath("//ul[@class='jal-item-list']/li/a/@href").extract()
    # 免疫规划处理每篇文章url逻辑
    item_urls_bottom2 = article_sel.xpath("//dl[@class='item-dl']/dd//a[@class='item-text']/@href").extract()

    item_urls_bottom = item_urls_bottom1 if len(item_urls_bottom1) else item_urls_bottom2
    for bottom_url in item_urls_bottom:
        deal_article_content(article_url, bottom_url, category)
        # 启动多线程 **********************
        # executor.submit(deal_article_content, article_url, bottom_url, category)
    try:
        # 处理下一页逻辑
        next_page_url = article_sel.xpath("//a[contains(text(), '下一页')]/@href").extract()[0]
        next_page_url = next_page_url.strip()
        next_page_url = parse.urljoin(article_url, next_page_url, category)
        deal_article_page(next_page_url, category)
        # 启动多线程 **********************
        # executor.submit(deal_article_page, next_page_url, category)
    except:
        # print("该主题下已无下一页！")
        return


def deal_article_content(previous_url, article_url, category):
    """
    处理单个文章内容
    :param previous_url: 文章前半段url
    :param article_url: 单个文章url
    :param category: 文章分类名称
    :return:
    """
    article_url = article_url.strip()
    if 'html' in article_url:
        url = parse.urljoin(previous_url, article_url)
        # print(url, category)
        if domain in url:
            res = requests.get(url, headers=headers).text
            res_sel = Selector(text=res)
            try:
                article_title = res_sel.xpath("//p[@class='cn-main-title']/text()").extract()[0]
            except IndexError as e:
                article_title = res_sel.xpath("//p[@class='cn-main-title']/font/text()").extract()[0]
            create_time = res_sel.xpath("//span[@class='info-date']/text()").extract()[0]
            createtime = datetime.strptime(create_time, '%Y-%m-%d')
            content = res_sel.xpath("//div[@class='cn-main-detail']").extract()[0]
            # save_article(article_title, createtime, category, content, url, '中国疾病预防控制中心')
            task = executor.submit(save_article, article_title, createtime, category, content, url, '中国疾病预防控制中心')
            wait([task])
        else:
            # print("该文章引用了其他来源地址！")
            if 'http://news.sciencenet.cn/' in url:
                res = requests.get(url, headers=headers).content
                res_text = res.decode('utf-8', 'ignore').encode('utf-8', 'ignore')
                res_sel = Selector(text=res_text)
                article_title = res_sel.xpath(".//*[@id='content1']/table//tr[3]/td/text()").extract()[0]
                create_time = res_sel.xpath("//*[@id='content']//tr[1]/td/div[1]/text()").extract()[-1]
                create_time = create_time.split('：')[-1].split(' ')[0].replace('/', '-')
                createtime = datetime.strptime(create_time, '%Y-%m-%d')
                content_list = res_sel.xpath("//*[@id='content1']/p").extract()
                content = '\n\t'.join(content_list)
                # save_article(article_title, createtime, category, content, url, '中国疾病预防控制中心')
                task = executor.submit(save_article, article_title, createtime, category, content, url, '中国疾病预防控制中心')
                wait([task])
    else:
        return


def save_article(title, createtime, category_name, content, note, source):
    article = t_article()
    keyword = category_name if category_name in content else ''
    article.article_id = uuid.uuid1()
    article.category_name = category_name
    article.title = title
    article.keyword = keyword
    article.symptom = ''
    article.content = content
    article.source = source
    article.article_state = '0'
    article.check_option = ''
    article.createtime = createtime
    article.create_user_id = '2CEBCA185F4F4464B6017AB1C4BDB843'
    article.create_user_name = '超级管理员'
    now = datetime.now()
    now = datetime.strftime(now, "%Y-%m-%d %H:%M:%S")
    article.update_time = now
    article.update_user_id = '2CEBCA185F4F4464B6017AB1C4BDB843'
    article.update_user_name = '超级管理员'
    article.note = note
    article.data_source_code = '2'
    article.data_source_name = '网络爬取'
    article.is_active = '-1'

    exist_article = t_article.select().where(t_article.note == article.note)
    if exist_article:
        article.save()
    else:
        article.save(force_insert=True)


def save_category(category_name, parent_name):
    category = t_category()

    uuid_str = uuid.uuid1()
    category.category_id = uuid_str
    category.category_name = category_name
    parent_id = t_category.get(t_category.category_name == parent_name) if parent_name else ''
    category.parent_id = parent_id
    level = 2 if parent_name else 1
    category.level = level
    level_code = parent_id if parent_name else uuid_str
    category.level_code = level_code
    now = datetime.now()
    now = datetime.strftime(now, "%Y-%m-%d %H:%M:%S")
    category.create_time = now
    category.create_user_id = '2CEBCA185F4F4464B6017AB1C4BDB843'
    category.create_user_name = '超级管理员'
    category.update_time = now
    category.update_user_id = '2CEBCA185F4F4464B6017AB1C4BDB843'
    category.update_user_name = '超级管理员'
    category.note = ''
    category.organization_name = ''

    exist_category = t_category.select().where(t_category.category_name == category.category_name)
    if exist_category:
        return
    else:
        category.save(force_insert=True)


def get_health(urls):
    print("开始爬取健康知识！", len(urls))
    for url in urls:
        # get_health_article(url)
        task = executor.submit(get_health_article, url)
        wait([task])
    print("爬取健康知识完成！")


def get_cdc(urls):
    print("开始爬取疾控知识！")
    for item in urls:
        # get_topic(item)
        # 启动多线程 **********************
        task = executor.submit(get_topic, item)
        wait([task])
    print("爬取疾控知识完成！")


if __name__ == "__main__":
    executor = ThreadPoolExecutor(max_workers=10)

    all_topic_urls = get_article_urls()
    save_category('健康知识', '')
    # 获取到健康知识每一页的url
    get_health_urls(domain_health)
    print(health_urls)
    urls_task = executor.submit(get_health_urls, domain_health)
    health = executor.submit(get_health, health_urls)
    cdc = executor.submit(get_cdc, all_topic_urls)
    wait([urls_task, health, cdc, ], return_when=ALL_COMPLETED)
    print("end ")
