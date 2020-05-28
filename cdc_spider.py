import logging
import re
import uuid
from datetime import datetime
from urllib import parse
from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
import js2py
from apscheduler.schedulers.background import BlockingScheduler
from scrapy import Selector
import requests
from email.mime.text import MIMEText
# # import smtplib
# from smtplib import SMTP_SSL
# from email.header import Header

from cdc_models_formal import t_article as t_article_test, t_category as t_category_test, \
    t_article_category as middel_test
from cdc_models import t_article as t_article_formal, t_category as t_category_formal, \
    t_article_category as middel_formal

unspider_title = ['烟草控制', '妇幼保健']
domain = 'http://www.chinacdc.cn/jkzt/'
domain_health = 'http://www.jkb.com.cn/healthyLiving/jkzs/'
health_urls = []
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.113 Safari/537.36'
}
headers_health = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36',
}
organization_dict = {'传染病': '急性传染病预防控制室', '突发公共卫生事件': '卫生应急管理室', '慢性非传染性疾病': '地方病与慢性病防治室', '营养与健康': '营养与学生健康检测室',
                     '环境与健康': '环境卫生室', '职业卫生与中毒控制': '职业卫生室', '辐射防护': '辐射安全室'}
from_addr = "502258389@qq.com"
to_addr = "2581177069@qq.com"
password = "rrzbldfkcfbkcbea"
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    filename='log.txt',
                    filemode='a')
scheduler = BlockingScheduler()


def my_listener(event):
    if event.exception:
        # sendMail('爬取疾控中心任务运行失败，请检查原因！')
        logging.info('任务出现异常！')
    else:
        logging.info('任务照常运行...')


scheduler.add_listener(my_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
scheduler._logger = logging


def get_article_urls():
    # 请求健康主题页面
    res_text = requests.get(domain, headers=headers).text
    sel = Selector(text=res_text)
    # 获取所有主题url
    all_urls = sel.xpath("//ul[@class='sr-ul']/li/a/@href").extract()
    return all_urls


def get_521_content(url):
    req = requests.get(url=url, headers=headers_health)
    cookies = req.cookies
    cookies = '; '.join(['='.join(item) for item in cookies.items()])
    txt_521 = req.text
    txt_521 = ''.join(re.findall('<script>(.*?)</script>', txt_521))
    return (txt_521, cookies, req)


def fixed_fun(function, url):
    print(function)
    js = function.replace("<script>", "").replace("</script>", "").replace("{eval(", "{var my_data_1 = (")
    # print(js)
    # 使用js2py的js交互功能获得刚才赋值的data1对象
    context = js2py.EvalJs()
    context.execute(js)
    js_temp = context.my_data_1
    print(js_temp)
    index1 = js_temp.find("document.")
    index2 = js_temp.find("};if((")
    js_temp = js_temp[index1:index2].replace("document.cookie", "my_data_2")
    new_js_temp = re.sub(r'document.create.*?firstChild.href', '"{}"'.format(url), js_temp)
    # print(new_js_temp)
    # print(type(new_js_temp))

    context.execute(new_js_temp)
    if context.my_data_2:
        data = context.my_data_2
    else:
        js_temp = js_temp[index1:index2].replace("document.cookie", "my_data_2")
        new_js_temp = re.sub(r'document.create.*?firstChild.href', '"{}"'.format(url), js_temp)
        data = context.my_data_2
    # print(data)
    __jsl_clearance = str(data).split(';')[0]
    return __jsl_clearance


def get_health_req(url):
    for i in range(2, 2000):
        txt_521, cookies, req = get_521_content(url)
        if req.status_code == 521:
            __jsl_clearance = fixed_fun(txt_521, url)
            headers_health['Cookie'] = __jsl_clearance + ';' + cookies
            res1 = requests.get(url=url, headers=headers_health)
            if res1.status_code == 200:
                return res1
            else:
                continue
        else:
            return req


def get_health_urls(url):
    res = get_health_req(url)
    res_health = res.content
    res_text = res_health.decode('utf-8', 'ignore').encode('utf-8', 'ignore')
    health_sel = Selector(text=res_text)
    urls = health_sel.xpath("//div[@class='mainL fl']/ul/li/div[@class='txt']/h4/a/@href").extract()
    for url in urls:
        health_urls.append(url)
    try:
        # 处理下一页逻辑
        next_page_url = health_sel.xpath("//ul[@class='pagination']/li/a/@href").extract()[-1]
        get_health_urls(next_page_url)
    except Exception as e:
        logging.info("获取健康知识url完成")
        return


def get_health_article(url):
    res_article = requests.get(url, headers=headers_health).content
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
            # print(crb_level2_category, crb_article_url)
            deal_article_page(crb_article_url, '传染病')
            # 启动多线程 **********************
            # task1 = executor.submit(deal_article_page, crb_article_url, crb_level2_category)
            # wait([task1], return_when=ALL_COMPLETED)
    else:
        # 一级分类名称
        disease_category = next_page_sel.xpath("//div[@class='cn-title']/p/text()").extract()[0]
        topic = next_page_sel.xpath("//h2[@class='method-item-title']/a/text()").extract()[0]
        if topic == '中毒有关知识':
            next_page_topic = next_page_sel.xpath("//h2[@class='method-item-title']/a/text()").extract()[1]
            next_page_url = next_page_sel.xpath("//h2[@class='method-item-title']/a/@href").extract()[1]
        else:
            next_page_topic = next_page_sel.xpath("//h2[@class='method-item-title']/a/text()").extract()[0]
            next_page_url = next_page_sel.xpath("//h2[@class='method-item-title']/a/@href").extract()[0]
        if disease_category not in unspider_title:
            # 保存一级分类
            save_category(disease_category, '')
            if next_page_topic == '知识天地':
                # 处理不带有二级分类的文章
                article_url = parse.urljoin(next_url, next_page_url)
                deal_article_page(article_url, disease_category)
                # 启动多线程 **********************
                # task2 = executor.submit(deal_article_page, article_url, disease_category)
                # wait([task2], return_when=ALL_COMPLETED)
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

                        deal_article_page(level3_url, disease_category)
                        # 启动多线程 **********************
                        # task3 = executor.submit(deal_article_page, level3_url, item_category)
                        # wait([task3])
                        continue
                    deal_article_page(levele2_url, disease_category)
                    # 启动多线程 **********************
                    # task4 = executor.submit(deal_article_page, levele2_url, level2_category)
                    # wait([task4])
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
            content = daal_img(content, url)
            save_article(article_title, createtime, category, content, url, '中国疾病预防控制中心')
            # task = executor.submit(save_article, article_title, createtime, category, content, url, '中国疾病预防控制中心')
            # wait([task])
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
                content = daal_img(content, url)
                save_article(article_title, createtime, category, content, url, '中国疾病预防控制中心')
                # task = executor.submit(save_article, article_title, createtime, category, content, url, '中国疾病预防控制中心')
                # wait([task])
    else:
        return


def daal_img(content, url):
    """
    转换文章图片src属性
    :param content: 文章内容
    :param previous_url: 图片前置url
    :return: 转换图片src后的文章内容
    """
    info_src = re.findall(r'\ssrc="(.*jpg)"\s', content)
    info_href = re.findall(r'\shref="(.*)"\s', content)
    if len(info_src):
        url_list = url.split('/')[:-1]
        url_join = '/'.join(url_list) + '/'
        for item in info_src:
            url_new = parse.urljoin(url_join, item)
            content = content.replace(item, url_new)
    if len(info_href):
        url_list = url.split('/')[:-1]
        url_join = '/'.join(url_list) + '/'
        for item in info_href:
            url_new = parse.urljoin(url_join, item)
            content = content.replace(item, url_new)
    return content


def save_article(title, createtime, category_name, content, note, source):
    article = t_article_test()
    article_formal = t_article_formal()

    m_test = middel_test()
    m_formal = middel_formal()

    keyword = category_name if category_name in content else None
    id = uuid.uuid1()
    article_formal.article_id = article.article_id = id
    article_formal.category_name = article.category_name = category_name

    category_id_test = t_category_test.get(t_category_test.category_name == category_name).category_id
    category_id_formal = t_category_formal.get(t_category_formal.category_name == category_name).category_id

    m_test.article_id = article.article_id
    m_test.category_id = category_id_test

    m_formal.article_id = article.article_id
    m_formal.category_id = category_id_formal

    article_formal.title = article.title = title
    article_formal.keyword = article.keyword = keyword
    # article_formal.symptom = article.symptom = null
    article_formal.content = article.content = content
    article_formal.source = article.source = source
    article_formal.article_state = article.article_state = '0'
    # article_formal.CHECK_OPINION = article.CHECK_OPINION = ''
    article_formal.create_time = article.create_time = createtime
    article_formal.create_user_id = article.create_user_id = '2CEBCA185F4F4464B6017AB1C4BDB843'
    article_formal.create_user_name = article.create_user_name = '超级管理员'
    now = datetime.now()
    now = datetime.strftime(now, "%Y-%m-%d %H:%M:%S")
    article_formal.update_time = article.update_time = now
    article_formal.update_user_id = article.update_user_id = '2CEBCA185F4F4464B6017AB1C4BDB843'
    article_formal.update_user_name = article.update_user_name = '超级管理员'
    article_formal.note = article.note = note
    article_formal.data_source_code = article.data_source_code = '2'
    article_formal.data_source_name = article.data_source_name = '网络爬取'
    article_formal.is_active = article.is_active = '-1'
    try:
        exist_article_test = t_article_test.select().where(t_article_test.note == article.note)
        if exist_article_test:
            pass
            # logging.info("url为 {} 的文章已存在，不做操作！".format(note))
        else:
            article.save(force_insert=True)
            m_test.save(force_insert=True)
    except Exception as e:
        pass
    try:
        exist_article_formal = t_article_formal.select().where(t_article_formal.note == article.note)
        if exist_article_formal:
            pass
            # logging.info("formal中url为 {} 的文章已存在，不做操作！".format(note))
        else:
            article_formal.save(force_insert=True)
            m_formal.save(force_insert=True)
    except Exception as e:
        pass


def save_category(category_name, parent_name):
    category = t_category_test()
    category_formal = t_category_formal()
    uuid_str = uuid.uuid1()
    category_formal.category_id = category.category_id = uuid_str
    category_formal.category_name = category.category_name = category_name
    if parent_name:
        parent_id = t_category_test.get(t_category_test.category_name == parent_name)
        category_formal.parent_id = category.parent_id = parent_id
    else:
        parent_id = None
        organization_name = organization_dict.get(category_name, None)
        category.ORGANIZATION_NAME = category_formal.ORGANIZATION_NAME = organization_name
    level = 2 if parent_name else 1
    category_formal.level = category.level = level
    level_code = parent_id if parent_name else uuid_str
    category_formal.level_code = category.level_code = level_code
    now = datetime.now()
    now = datetime.strftime(now, "%Y-%m-%d %H:%M:%S")
    category_formal.create_time = category.create_time = now
    category_formal.create_user_id = category.create_user_id = '2CEBCA185F4F4464B6017AB1C4BDB843'
    category_formal.create_user_name = category.create_user_name = '超级管理员'
    category_formal.update_time = category.update_time = now
    category_formal.update_user_id = category.update_user_id = '2CEBCA185F4F4464B6017AB1C4BDB843'
    category_formal.update_user_name = category.update_user_name = '超级管理员'
    category_formal.note = category.note = ''
    category_formal.organization_name = category.organization_name = ''

    exist_category = t_category_test.select().where(t_category_test.category_name == category.category_name)
    exist_category_formal = t_category_formal.select().where(t_category_formal.category_name == category.category_name)
    if exist_category:
        pass
        # logging.info("名称为 {} 的类别已存在，不做操作！".format(category_name))
    else:
        category.save(force_insert=True)
    if exist_category_formal:
        pass
        # logging.info("formal中名称为 {} 的类别已存在，不做操作！".format(category_name))
    else:
        category_formal.save(force_insert=True)


def get_health(urls):
    logging.info("开始爬取健康知识!")
    for url in urls:
        # get_health_article(url)
        task = executor.submit(get_health_article, url)
        wait([task])
    logging.info("爬取健康知识完成！")


def get_cdc(urls):
    logging.info("开始爬取疾控知识！")
    for item in urls:
        # get_topic(item)
        # 启动多线程 **********************
        task = executor.submit(get_topic, item)
        wait([task])
    logging.info("爬取疾控知识完成！")


# def sendMail(mail_content):
#     # mail_content = 'This is a content of the mail'
#     try:
#         content = MIMEText(mail_content, 'plain',
#                            'utf-8')  # 第一个参数：邮件的内容；第二个参数：邮件内容的格式，普通的文本，可以使用:plain,如果想使内容美观，可以使用:html；第三个参数：设置内容的编码，这里设置为:utf-8
#         reveivers = Header(to_addr)
#         content['To'] = reveivers  # 设置邮件的接收者，多个接收者之间用逗号隔开
#         content['From'] = Header(from_addr)  # 邮件的发送者,最好写成str("这里填发送者")，不然可能会出现乱码
#         content['Subject'] = Header("爬虫每日结果推送")  # 邮件的主题
#
#         ##############使用qq邮箱的时候，记得要去开启你的qq邮箱的smtp服务；##############
#         # 方法：
#         # 1）登录到你的qq邮箱；
#         # 2）找到首页顶部的【设置】并点击；
#         # 3）找到【账户】这个选项卡并点击，然后在页面中找到“SMTP”相关字样，找到【开启】的超链接，点击后会告诉你开启方法（需要发个短信），然后按照指示操作，最终会给你一个密码，这个密码可以用于在代码中当作邮箱密码
#         # 注意!!!:163邮箱之类的不知道要不要这些操作，如果是163邮箱你可以忽略此步骤
#         ###########################################################################
#         smtp_server = SMTP_SSL("smtp.qq.com",
#                                        465)  # 第一个参数：smtp服务地址（你发送邮件所使用的邮箱的smtp地址，在网上可以查到，比如qq邮箱为smtp.qq.com） 第二个参数：对应smtp服务地址的端口号
#         smtp_server.login(from_addr, password)  # 第一个参数：发送者的邮箱账号 第二个参数：对应邮箱账号的密码
#         #################################
#
#         smtp_server.sendmail(from_addr, ["2581177069@qq.com", "502258389@qq.com"],
#                              content.as_string())  # 第一个参数：发送者的邮箱账号；第二个参数是个列表类型，每个元素为一个接收者；第三个参数：邮件内容
#         smtp_server.quit()  # 发送完成后加上这个函数调用，类似于open文件后要跟一个close文件一样
#     except Exception as e:
#         print(e)


@scheduler.scheduled_job('cron', month='1-12', day='1-31', hour='00', minute='02', second='0')
def main():
    all_topic_urls = get_article_urls()
    save_category('健康知识', '')
    # 获取到健康知识每一页的urls
    get_health_urls(domain_health)
    health = executor.submit(get_health, health_urls)
    cdc = executor.submit(get_cdc, all_topic_urls)
    wait([health, cdc], return_when=ALL_COMPLETED)
    # now = datetime.now()
    # now = datetime.strftime(now, "%Y-%m-%d %H:%M:%S")
    # sendMail('{}爬取疾控中心任务运行成功！'.format(now))


if __name__ == "__main__":
    executor = ThreadPoolExecutor(max_workers=10)
    # main()
    with open('log.txt', 'a', encoding='utf8') as f:
        try:
            scheduler.start()
            f.write('任务运行成功!\n')
        except Exception:
            scheduler.shutdown()
            # sendMail('爬取疾控中心任务运行失败，请检查原因！')
            f.write('***********************任务运行失败!*****************************\n')
