#-*-coding:utf-8-*-
# Author:    kuangggg
#犀牛之星企业库信息的采集程序

import MySQLdb
import sys
import re
import math
import datetime
import codecs
import json

reload(sys)
sys.setdefaultencoding('utf-8')


#======自定制邮箱助手
class MailHelper():
    #加载服务邮箱配置
    def __init__(self):
        conf = ConfigParser.ConfigParser()
        with codecs.open('conf.ini', encoding="utf-8-sig" ) as f:
            conf.readfp(f)
            self.smtp_server = conf.get("smtp", "smtp_server")
            self.from_addr = conf.get("smtp", "from_addr")
            self.pwd = conf.get("smtp", "pwd")
    def _format_addr(self, s):
        name, addr = parseaddr(s)
        return formataddr(( \
            Header(name, 'utf-8').encode(), \
            addr.encode('utf-8') if isinstance(addr, unicode) else addr))

    def send_mail(self, from_user, to_addr, subject, content):
        msg = MIMEText(content, 'html', 'utf-8')
        msg['From'] = self._format_addr('%s<%s>' %(from_user, self.from_addr))
        msg['To'] = self._format_addr('管理员<%s>' %to_addr)
        msg['Subject'] = Header(subject, 'utf-8').encode()
        try:
            server = smtplib.SMTP(self.smtp_server, 25)
            server.login(self.from_addr, self.pwd)
            server.sendmail(self.from_addr, to_addr, msg.as_string())
            server.close()
            return True
        except Exception, e:
            return False

#=======犀牛之星爬虫控制类
class XiniuSpider():
    def __init__(self):
        try:
            #加载配置
            conf = ConfigParser.ConfigParser()
            with codecs.open('conf.ini', encoding="utf-8-sig") as f:
                conf.readfp(f)
            # 输入到文件的日志
            self.logger = logging.getLogger('spider')
            self.logger.setLevel(logging.INFO)
            fh = logging.FileHandler(conf.get('xiniu_log', 'path'))
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)
            try:
                self.conn = MySQLdb.connect(
                    host = conf.get("db", "host"),
                    port = int(conf.get("db", "port")),
                    user = conf.get("db", "user"),
                    passwd = conf.get("db", "passwd"),
                    db = conf.get("db", "db_name"),
                    charset = 'utf8')
                #数据库游标
                self.cursor = self.conn.cursor()
                self.logger.info("数据库连接成功")
            except Exception as e:
                self.logger.info("数据库连接异常 : %s" % e)
            self.logger.info('配置加载完毕')
        except Exception as e:
            self.logger.info("配置加载失败 : %s" % e)
    def req(self, url):
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.3; WOW64; rv:43.0) Gecko/20100101 Firefox/43.0'}
        try:
            response = requests.get(url, timeout=4, headers=headers).content
            return response.decode('utf-8')
        except Exception as e:
            self.logger.info("请求连接失效 : %s" % e)
            return False
    #解析页码
    def parse_pages(self):
        url = "http://www.ipo3.com/company-ajax_items.html"
        content = self.req(url)
        try:
            pattern = re.compile(r'company_count.*?=(.*?);')
            count = re.findall(pattern, content)[0].strip()
            return int(math.ceil(float(count) / 30))
        except Exception as e:
            self.logger.info("页码解析错误 : %s" % e)
            time.sleep(60)
            self.parse_pages()
    #股票基本信息
    def baseinfo(self, name, code, zbqs):
        url_baseinfo = "http://www.ipo3.com/company-show/stock_code-%s.html" % code
        response = self.req(url_baseinfo)
        if response == False:
            return
        selector = etree.HTML(response)
        des = selector.xpath('//div[@class="companyprofile"]/p[2]')[0]
        # 转让方式,判定是否存在
        if des.xpath('span[1]/text()'):
            zrfs = des.xpath('span[1]/text()')[0].strip()
        else:
            zrfs = ''
        # 公司全称
        if des.xpath('span[2]/text()'):
            fullname = des.xpath('span[2]/text()')[0].strip()
        else:
            fullname = ''
        # 注册地址
        if des.xpath('span[3]/text()'):
            reg_add = des.xpath('span[3]/text()')[0].strip()
        else:
            reg_add = ''
        # 公司网址
        if des.xpath('span[4]/a'):
            gswz = des.xpath('span[4]/a/@href')[0].strip()
        else:
            gswz = ''
        # 行业
        if des.xpath('span[5]/text()'):
            hy = des.xpath('span[5]/text()')[0].strip()
        else:
            hy = ''
        # 历史前沿
        url_lsyg = "http://www.ipo3.com/company-ajax_total/stock_code-%s.html" % code
        response = self.req(url_lsyg)
        if response == False:
            return
        selector = etree.HTML(response)
        divs = selector.xpath('//div[@class="edit-panel bf"]')[1:]
        content = ''
        for div in divs:
            title = div.xpath('div/div/span/text()')[0]
            if div.xpath('div/p/text()'):
                content = title + '|' + div.xpath('div/p/text()')[0].strip() + '||' + content
            else:
                content = content + ''
        sql_chk = "select `code` from baseinfo where code = '%s'" % code
        if self.cursor.execute(sql_chk) > 0:
            try:
                list = (name, fullname, reg_add, hy, gswz, zrfs, zbqs, content, code)
                sql = "update baseinfo set name=%s, fullname=%s, reg_add=%s, hy=%s, gswz=%s, zrfs=%s, zbqs=%s, lsyg=%s where code=%s"
                self.cursor.execute(sql, list)
                self.conn.commit()
                self.logger.info('股票代码 : %s 基本信息更新完成 ...' % code)
            except Exception as e:
                self.conn.rollback()
                msg = '股票代码 %s 基本信息更新失败 ,错误信息 : %s' % (code, e)
                self.logger.info(msg)
        else:
            try:
                list = (code, name, fullname, reg_add, hy, gswz, zrfs, zbqs, content)
                sql = "insert into baseinfo (code, name, fullname, reg_add, hy, gswz, zrfs, zbqs, lsyg)values(%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                self.cursor.execute(sql, list)
                self.conn.commit()
                msg = '股票代码 : %s 基本信息入库完成' % code
                self.logger.info(msg)
            except Exception as e:
                self.conn.rollback()
                msg = '股票代码 : %s 基本信息入库失败, 错误信息 : %s' % (code, e)
                self.logger.info(msg)
    #财政摘要
    def finance(self, code):
        url_finance = "http://www.ipo3.com/company-ajax_finance/stock_code-%s.html" % code
        response = self.req(url_finance)
        if response == False:
            return
        selector = etree.HTML(response)
        year1 = selector.xpath('/html/body/div[1]/div//dt/span[2]/text()')[0].strip()
        year2 = selector.xpath('/html/body/div[1]/div//dt/span[3]/text()')[0].strip()
        divs = selector.xpath('//div[@class="table-row"]')
        if divs.__len__() != 0:
            lists = []
            for div in divs:
                subject = div.xpath('span[1]/text()')[0].strip()
                data1 = div.xpath('span[2]/text()')[0].strip()
                list = (code, year1, subject, data1)
                lists.append(list)
            for div in divs:
                subject = div.xpath('span[1]/text()')[0].strip()
                data2 = div.xpath('span[3]/text()')[0].strip()
                list = (code, year2, subject, data2)
                lists.append(list)

            sql_chk = "select `code` from finance where code = '%s'" % code
            if self.cursor.execute(sql_chk) > 0:
                try:
                    sql = "delete from finance where code= '%s'" % code
                    self.cursor.execute(sql)
                    self.conn.commit()
                    sql = "insert into finance (code, year, subject, data) values (%s, %s, %s, %s)"
                    self.cursor.executemany(sql, lists)
                    self.conn.commit()
                    msg = '股票代码 : %s 财政摘要更新完成 ...' % code
                    self.logger.info(msg)
                except Exception, e:
                    self.conn.rollback()
                    msg = '股票代码 : %s 财政摘要更新失败,错误信息 : %s' % (code, e)
                    self.logger.info(msg)
            else:
                try:
                    sql = "insert into finance (code, year, subject, data) values (%s, %s, %s, %s)"
                    self.cursor.executemany(sql, lists)
                    self.conn.commit()
                    msg = '股票代码 : %s 财政摘要入库完成 ...' % code
                    self.logger.info(msg)
                except Exception, e:
                    self.conn.rollback()
                    msg = '股票代码 : %s 财政摘要入库失败 ,错误信息 : %s' % (code, e)
                    self.logger.info(msg)
    #十大股东
    def shareholder(self, code):
        cursor = self.conn.cursor()
        url_shareholder = "http://www.ipo3.com/company-ajax_shareholder/stock_code-%s.html" % code
        response = self.req(url_shareholder)
        if response == False:
            return
        selector = etree.HTML(response)
        rows = selector.xpath('/html/body/div[1]/div/div[2]/div[2]/div/dl/dd/div')
        lists = []
        if rows.__len__() != 0:
            for row in rows:
                list = (code, row.xpath('span[1]/text()')[0].strip(), row.xpath('span[2]/text()')[0].strip(),
                        row.xpath('span[3]/text()')[0].strip(), row.xpath('span[4]/text()')[0].strip())
                lists.append(list)

            sql_chk = "select `code` from stockholder where code = '%s'" % code
            if cursor.execute(sql_chk) > 0:
                try:
                    sql = "delete from stockholder where code='%s'" % code
                    self.cursor.execute(sql)
                    self.conn.commit()
                    sql = "insert into stockholder (code, gdmc, cgs, cgbl, gfxz) values (%s, %s, %s, %s, %s)"
                    cursor.executemany(sql, lists)
                    msg = '股票代码 : %s 十大股东更新完成 ...' %code
                    self.logger.info(msg)
                    self.conn.commit()
                except Exception as e:
                    self.conn.rollback()
                    msg = '股票代码 : %s 十大股东入更新失败,错误信息 : %s' % (code, e)
                    self.logger.info(msg)
            else:
                try:
                    sql = "insert into stockholder (code, gdmc, cgs, cgbl, gfxz) values (%s, %s, %s, %s, %s)"
                    cursor.executemany(sql, lists)
                    self.conn.commit()
                    msg = '股票代码 : %s 十大股东入库完成 ...' %code
                    self.logger.info(msg)
                except Exception as e:
                    self.conn.rollback()
                    msg = '股票代码 : %s 十大股东入库失败,错误信息 : %s' % (code, e)
                    self.logger.info(msg)
    #高管人员
    def manager(self, code):
        url_manager = "http://www.ipo3.com/company-ajax_shareholder/stock_code-%s.html" % code
        response = self.req(url_manager)
        if response == False:
            return
        selector = etree.HTML(response)
        divs = selector.xpath('/html/body/div[1]/div[1]/div[3]//div[@class="table-row"]')
        lists = []
        if divs.__len__() != 0:
            for div in divs:
                name = div.xpath('span[1]/text()')[0].strip()
                duty = div.xpath('span[2]/text()')[0].strip()
                info = div.xpath('span[3]/text()')[0].strip().split(' ')
                # 这里要进行一定的判定,样式会乱
                sex = info[0]
                birthdate = ''
                education = ''
                if info.__len__() > 2:
                    birthdate = info[2]
                if info.__len__() > 3:
                    education = info[3]
                list = (code, name, duty, birthdate, sex, education)
                lists.append(list)
            sql_chk = "select `code` from ggry where code = '%s'" % code
            if self.cursor.execute(sql_chk) > 0:
                try:
                    sql = "delete from ggry where code='%s'" % code
                    self.cursor.execute(sql)
                    self.conn.commit()
                    sql = "insert into ggry (code, name, duty, birthdate, sex, education) values (%s, %s, %s, %s, %s, %s)"
                    self.cursor.executemany(sql, lists)
                    self.conn.commit()
                    msg = '股票代码 : %s 高管人员更新完成 ...' % code
                    self.logger.info(msg)
                except Exception as e:
                    self.conn.rollback()
                    msg = '股票代码 : %s 高管人员更新失败,错误信息 : %s' % (code, e)
                    self.logger.info(msg)
            else:
                try:
                    sql = "insert into ggry (code, name, duty, birthdate, sex, education) values (%s, %s, %s, %s, %s, %s)"
                    self.cursor.executemany(sql, lists)
                    msg = '股票代码 : %s 高管人员入库完成 ...' %code
                    self.logger.info(msg)
                except Exception as e:
                    self.conn.rollback()
                    msg = '股票代码 : %s 高管人员入库失败,错误信息 : %s' % (code, e)
                    self.logger.info(msg)
                else:
                    self.conn.commit()
    def run(self):
        while True:
            self.crawl()
    def crawl(self):
        global block_xiniu
        block_xiniu = True
        start_time = datetime.datetime.now()
        stock_count = 0
        for i in range(1, self.parse_pages() + 1):
            url = 'http://www.ipo3.com/company-ajax_items/p-%s.html' % i
            response = self.req(url)
            selector = etree.HTML(response)
            divs = selector.xpath('/html/body/div[1]/div[2]/div[3]/div')[0:-1]
            for div in divs:
                code = div.xpath('ul/li[1]/div[2]/span/text()')[0][-6:]
                if block_xiniu == False:
                    end_time = datetime.datetime.now()
                    use_time = (end_time - start_time).seconds
                    msg = """
-------------------------
数据采集完毕

本次采集耗时 : %ss
采集股票个数 : %s

        """%(use_time, stock_count)
                    self.logger.info(msg)
                    quit()
                name = div.xpath('ul/li[1]/div[1]/a/text()')[0].strip()
                if div.xpath('ul/li[3]/text()'):
                    zbqs = div.xpath('ul/li[3]/text()')[0].strip()
                else:
                    zbqs = ''
                # ==================
                self.baseinfo(name, code, zbqs)
                self.finance(code)
                self.shareholder(code)
                self.manager(code)
                stock_count = stock_count + 1
                # ===================
        end_time = datetime.datetime.now()
        use_time = (end_time - start_time).seconds
        msg = """
-------------------------
数据采集完毕

本次采集耗时 : %s
采集股票个数 : %s

        """%(use_time,stock_count)
        self.logger.info(msg)
    def __del__(self):
        self.conn.close()
        self.cursor.close()

import wx
import thread
import win32api
import urllib2
import requests
from lxml import etree
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import parseaddr, formataddr
import logging
import time
import os
import ConfigParser
import pickle

class MyLogHandler(logging.Handler):
    def __init__(self, obj):
        logging.Handler.__init__(self)
        self.Object = obj
    def emit(self, record):
        tstr = time.strftime('%m-%d %H:%M:%S')
        try:
            self.Object.AppendText("[%s] %s\n" % (tstr, record.getMessage()))
        except Exception as e:
            pass
class WeiboScan():
    def __init__(self):
        #加载配置
        self.conf = ConfigParser.ConfigParser()
        with codecs.open('conf.ini', encoding="utf-8-sig" ) as f:
            self.conf.readfp(f)
        #实例化邮箱助手
        self.mail = MailHelper()
        #时间间隔
        self.timer = self.conf.get("weibo_cron", "timer")
        #日志配置
        self.log_path = self.conf.get("weibo_log", "path")
        # 输入到文件的日志
        self.logger = logging.getLogger('weibo')
        self.logger.setLevel(logging.INFO)
        fh = logging.FileHandler(self.conf.get('weibo_log', 'path'))
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        self.logger.info('配置加载完毕')

    #===============模拟登陆，返回cookie
    def login(self):
        url_login = 'http://login.weibo.cn/login/'
        header = {'User-Agent' : 'Mozilla/5.0 (Windows NT 6.3; WOW64; rv:43.0) Gecko/20100101 Firefox/43.0'}
        request = urllib2.Request(url_login, headers=header)
        response = urllib2.urlopen(request).read()
        selector = etree.HTML(response)
        password = selector.xpath('//input[@type="password"]/@name')[0]
        vk = selector.xpath('//input[@name="vk"]/@value')[0]
        action = selector.xpath('//form[@method="post"]/@action')[0]
        capId = selector.xpath('//input[@name="capId"]/@value')[0]
        new_url = url_login + action
        img_src = selector.xpath('//img/@src')[0]
        img = requests.post(img_src).content
        with open('validate.jpg', 'wb') as f:
            f.write(img)
        code = raw_input('请输入验证码')
        data = {
           'mobile' : '18291421158@163.com',
           password : 'zhoukuan',
           'remember' : 'on',
           'backURL' : 'http://weibo.cn',
           'backTitle' : '手机新浪网',
           'tryCount' : '',
           'vk' : vk,
           'capId' : capId,
           'code' : code,
           'submit' : '登录'
        }
        req = requests.post(new_url, data, allow_redirects=False)
        #将cookies写入到文件中保存下来
        with open('cookie.txt', 'wb') as f:
            f.write(pickle.dumps(req.cookies))
        expires = time.time() + 2000000
        self.conf.set('cookies', 'expires', expires)
        self.conf.write(open('conf.ini', 'w'))

    #==========解析页面，要监听的内容
    def get_content(self):
        url = 'http://weibo.cn/kuangggg'
        with open('cookie.txt', 'rb') as f:
            cookie = pickle.load(f)
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.3; WOW64; rv:43.0) Gecko/20100101 Firefox/43.0'}
        try:
            html = requests.get(url, timeout=4, headers=headers, cookies=cookie, allow_redirects=False).content
            selector = etree.HTML(html)
            name = selector.xpath('//a[@class="nk"]/text()')[0].strip()
            content = selector.xpath('//span[@class="ctt"]')[0]
            content = content.xpath('string(.)').strip()
            time = selector.xpath('//span[@class="ct"]/text()')[0].strip()
            return (name, content, time)
        except Exception as e:
            self.logger.error("请求链接失效 : %s" % e)
            return False
    #======检测内容
    def check_content(self, data):
        if not os.path.exists('weibo.txt'):
            return True
        else:
            with open('weibo.txt', 'r') as f:
                exist = f.readlines()
                if data + '\n' in exist:
                    return False
                else:
                    return True
    #=======写入微博
    def save_content(self, data):
        with open('weibo.txt', 'a') as f:
            f.write(data + '\n')

    def run(self):
        global block_weibo
        block_weibo = True
        while block_weibo:
            self.logger.info('开始扫描')
            #邮件配置
            from_user = '新浪微博'
            mail_to_list = self.conf.get("weibo_mail", "mailto_list").split("|")
            #关注对象
            name = self.conf.get("weibo_target", "name").strip()
            allow_list = name.split('|')
            #判断cookie是否过期
            expires = self.conf.get('cookies', 'expires')
            now = time.time()
            if now > expires:
                self.logger.error('cookies 失效, 请重新模拟登录')
            content = self.get_content()
            if content == False:
                time.sleep(float(self.timer))
                continue
            #对最新微博尽心判断是否为需要微博
            if content[0] in allow_list:
                subject = content[0]+'的微博更新了'
                content = content[0]+' '+content[1]
                #内容对比，是否为新内容
                if self.check_content(content):
                    self.save_content(content)
                    self.logger.info(subject)
                    self.logger.info(content)

                    for mail_to in mail_to_list:
                        if self.mail.send_mail(from_user, mail_to, subject, content):
                            self.logger.info('邮件发送成功-'+mail_to)
                        else:
                            self.logger.error(content+'邮件发送失败-'+mail_to)
            if block_weibo == False:
                self.logger.info('扫描结束')
                quit()
            time.sleep(float(self.timer))
        self.logger.info('扫描结束')
class NeeqNewsScan():
    def __init__(self):
        try:
            #加载配置
            conf = ConfigParser.ConfigParser()
            with codecs.open('conf.ini', encoding="utf-8-sig" ) as f:
                conf.readfp(f)
                self.timer = float(conf.get("neeq_cron", "timer"))
                self.mail_to_list = conf.get("neeq_mail", "mailto_list").split("|")
                self.from_user = conf.get("neeq_mail", "from_user")
                self.path = conf.get("neeq_log", "path")
            #实例化邮箱助手
            self.mail = MailHelper()
            # 输入到文件的日志
            self.logger = logging.getLogger('neeq')
            self.logger.setLevel(logging.INFO)
            fh = logging.FileHandler(self.path)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)
            self.logger.info('配置加载完毕')
        except Exception as e:
            self.logger.info('配置加载失败 : %s' %e)
    def req(self, url):
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.3; WOW64; rv:43.0) Gecko/20100101 Firefox/43.0'}
        try:
            response = requests.get(url, timeout=4, headers=headers).content
            return response.decode('utf-8')
        except Exception as e:
            self.logger.info("请求连接失效 : %s" % e)
            return False
    def parse_content(self, content):
        try:
            selector = etree.HTML(content)
            date = selector.xpath('//div[@class="dynamic"]')[0].xpath('//p[@class="moon"]/text()')[0].strip()
            title = selector.xpath('//div[@class="dynamic"]')[0].xpath('//div[@class="content"]/h3/a/text()')[0].strip()
            url = selector.xpath('//div[@class="dynamic"]')[0].xpath('//div[@class="content"]/h3/a/@href')[0].strip()
            if 'detail?' in url:
                url = 'http://www.neeq.com.cn/'+url
                html = self.req(url)
                selector = etree.HTML(html)
                content = selector.xpath('//div[@class="articalcontent-detail"]')[0].xpath('string(.)')
            else:
                content = u'文档类型内容，详情查看官网'
            return (date, title, content)
        except Exception as e:
            self.logger.info('解析内容失败 %s' %e)
            return False
    def chk_content(self, data):
        if not os.path.exists('news.txt'):
            return True
        else:
            with open('news.txt', 'r') as f:
                exist = f.readlines()
                if data + '\n' in exist:
                    return False
                else:
                    return True
    def save_content(self, data):
        with open('news.txt', 'a') as f:
            f.write(data+'\n')
    def run(self):
        global block_neeq
        block_neeq = True
        while block_neeq:
            self.logger.info('扫描开始')
            url = 'http://www.neeq.com.cn/news_releases'
            content = self.req(url)
            content = self.parse_content(content)
            if content == False:
                time.sleep(float(self.timer))
                continue
            data = content[0]+'---'+content[1]
            if self.chk_content(data):
                self.logger.info(data)
                self.save_content(data)
                for mail_to in self.mail_to_list:
                    if self.mail.send_mail(self.from_user, mail_to, content[1], content[2]):
                        self.logger.info('邮件发送成功-'+mail_to)
                    else:
                        self.logger.error(content+'邮件发送失败-'+mail_to)
            if block_neeq == False:
                self.logger.info('扫描结束')
                quit()
            time.sleep(float(self.timer))
        self.logger.info('扫描结束')
class NeeqInfo():
    def __init__(self):
        try:
            #加载配置
            conf = ConfigParser.ConfigParser()
            with codecs.open('conf.ini', encoding="utf-8-sig" ) as f:
                conf.readfp(f)
                self.path = conf.get("info_log", "path")
            # 输入到文件的日志
            self.logger = logging.getLogger('info')
            self.logger.setLevel(logging.INFO)
            fh = logging.FileHandler(self.path)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)
            self.logger.info('配置加载完毕')
            try:
                self.conn = MySQLdb.connect(
                    host = conf.get("db", "host"),
                    port = int(conf.get("db", "port")),
                    user = conf.get("db", "user"),
                    passwd = conf.get("db", "passwd"),
                    db = conf.get("db", "db_name"),
                    charset = 'utf8')
                #数据库游标
                self.cursor = self.conn.cursor()
                self.logger.info("数据库连接成功")
            except Exception as e:
                self.logger.info("数据库连接失败 : %s" % e)
        except Exception as e:
            self.logger.info("配置加载失败 : %s" % e)
    #解析页码
    def parse_page(self):
        import time
        now = time.strftime("%Y-%m-%d")
        stamp = '%.3f' % time.time()
        stamp = stamp[:10]+stamp[-3:]
        url = 'http://www.neeq.cc/controller/GetDisclosureannouncementPage?type=1&company_cd=&key=&subType=0&startDate=2016-03-24&endDate='+now+'&queryParams=0&page=1&_='+stamp
        try:
            content = self.req(url)
            obj = json.loads(content)
            page_size = obj['pagingInfo']['pageSize']
            total_count = obj['pagingInfo']['totalCount']
            pages = int(math.ceil(float(total_count)/page_size))
            return pages
        except Exception as e:
            self.logger.error('页码解析错误 : %s' % e)
            time.sleep(60)
            self.parse_page()
    def req(self, url):
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.3; WOW64; rv:43.0) Gecko/20100101 Firefox/43.0'}
        try:
            response = requests.get(url, timeout=4, headers=headers).content
            return response.decode('utf-8')
        except Exception as e:
            self.logger.info("请求连接失效 : %s" %e)
            return False
    def run(self):
        while True:
            self._run()
    def _run(self):
        import time
        global block_info
        block_info = True
        start_time = datetime.datetime.now()
        gg_count = 0
        stamp = '%.3f' % time.time()
        stamp = stamp[:10]+stamp[-3:]
        now = time.strftime("%Y-%m-%d")
        pages = self.parse_page()
        for page in range(1, pages+1):
            url = 'http://www.neeq.cc/controller/GetDisclosureannouncementPage?type=1&company_cd=&key=&subType=0&startDate=2016-03-24&endDate='+now+'&queryParams=0&page='+str(page)+'&_='+stamp
            content = self.req(url)
            if content == False:
                continue
            obj = json.loads(content)
            data = obj['disclosureInfos']
            for row in data:
                if block_info == False:
                    end_time = datetime.datetime.now()
                    use_time = (end_time - start_time).seconds
                    msg = """
-------------------------
数据采集完毕

本次采集耗时 : %s
采集公告个数 : %s

        """%(use_time, gg_count)
                    self.logger.info(msg)
                    quit()
                code = row['companyCode']
                title = row['titleFull']
                date = row['uploadTimeString']
                link_add = 'http://file.neeq.com.cn/upload'+row['filePath']
                row = (code, title, date, link_add)
                sql = "insert into gsgg (code, title, date, link_add) values (%s, %s, %s, %s)"
                sql_chk = "select `id` from gsgg where link_add = '%s'" %link_add
                try:
                    flag = self.cursor.execute(sql_chk)
                    if flag > 0:
                        self.logger.info('['+code+']'+title+' - 已入库')
                    else:
                        try:
                            self.cursor.execute(sql, row)
                            self.conn.commit()
                            self.logger.info('['+code+']'+title+' - 入库')
                            gg_count = gg_count + 1
                        except Exception as e:
                            self.conn.rollback()
                            self.logger.error('['+code+']'+title+' - 入库失败')
                except Exception as e:
                    self.logger.info("数据库出错 : %s" % e)
                    continue

        end_time = datetime.datetime.now()
        use_time = (end_time - start_time).seconds
        msg = """
-------------------------
数据采集完毕

本次采集耗时 : %s
采集公告个数 : %s

        """%(use_time, gg_count)
        self.logger.info(msg)
#====================GUI

class info(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self.panel = wx.Panel
        self.text_info = wx.TextCtrl(parent=self, style=wx.TE_AUTO_SCROLL | wx.TE_MULTILINE, size=(600, 500))
        self.btn_start = wx.Button(parent=self, label=u"开始")
        self.btn_stop = wx.Button(parent=self, label=u"停止")
        self.btn_log = wx.Button(parent=self, label=u"日志")
        self.btn_clear = wx.Button(parent=self, label=u"清除日志")
        img = wx.Image(r'img/neeq.jpg', wx.BITMAP_TYPE_ANY).Scale(100, 100)
        self.img = wx.StaticBitmap(self, -1, wx.BitmapFromImage(img))
        self.text_info.SetEditable(False)
        self.grid = wx.GridBagSizer(5, 5)
        self.grid.Add(self.text_info, pos=(0, 0), flag=wx.ALL | wx.EXPAND, span=(7, 4), border=5)
        self.grid.Add(self.btn_start, pos=(0, 4), flag=wx.ALL | wx.ALIGN_CENTER, span=(1, 1), border=5)
        self.grid.Add(self.btn_stop, pos=(1, 4), flag=wx.ALL | wx.ALIGN_CENTER, span=(1, 1), border=5)
        self.grid.Add(self.btn_log, pos=(2, 4), flag=wx.ALL | wx.ALIGN_CENTER, span=(1, 1), border=5)
        self.grid.Add(self.btn_clear, pos=(3, 4), flag=wx.ALL | wx.ALIGN_CENTER, span=(1, 1), border=5)
        self.grid.Add(self.img, pos=(4, 4), flag=wx.ALL | wx.ALIGN_CENTER, span=(2, 1), border=5)
        self.SetSizer(self.grid)
        self.grid.AddGrowableCol(0, 1)
        self.grid.AddGrowableCol(1, 1)
        self.grid.AddGrowableCol(2, 1)
        self.grid.AddGrowableCol(3, 1)
        self.grid.AddGrowableCol(4, 1)
        self.grid.AddGrowableRow(0, 1)
        self.grid.AddGrowableRow(1, 1)
        self.grid.AddGrowableRow(2, 1)
        self.grid.AddGrowableRow(3, 1)
        self.grid.AddGrowableRow(4, 1)
        self.grid.AddGrowableRow(5, 1)
        self.grid.Fit(self)
        self.Bind(wx.EVT_BUTTON, self.onStart, self.btn_start)
        self.Bind(wx.EVT_BUTTON, self.onStop, self.btn_stop)
        self.Bind(wx.EVT_BUTTON, self.onLog, self.btn_log)
        self.Bind(wx.EVT_BUTTON, self.onClear, self.btn_clear)
        self.timer = None
        handler = MyLogHandler(self.text_info)
        logging.getLogger('info').addHandler(handler)
        conf = ConfigParser.ConfigParser()
        with codecs.open('conf.ini', encoding="utf-8-sig" ) as f:
            conf.readfp(f)
            self.log_path = conf.get("info_log", "path")
            self.cron = conf.get("info_cron", "cron")

    def OnTimerEvent(self, e):
        thread.start_new_thread(self.clear, (e,))
    def clear(self, e):
        if len(self.text_info.GetValue()) > 1024:
            self.text_info.Clear()


    def onStart(self, e):
        if self.timer:
            return
        self.btn_start.Disable()
        self.btn_stop.Enable()
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimerEvent)
        self.timer.Start(4000)
        thread.start_new_thread(self._run, (e,))
    def onStop(self, e):
        global block_info
        block_info = False
        self.btn_start.Enable()
        self.btn_stop.Disable()
        if not self.timer:
            return
        self.timer.Stop()
        self.timer = None
    def _run(self, e):

        info = NeeqInfo()
        info.run()

    def onLog(self, e):
        win32api.ShellExecute(0, 'open', self.log_path, '', '', 1)
    def onClear(self, e):
        with open(self.log_path, 'w') as f:
            f.truncate()

class xiniu(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self.panel = wx.Panel
        self.text = wx.TextCtrl(parent=self, style=wx.TE_AUTO_SCROLL | wx.TE_MULTILINE, size=(600, 500))
        self.btn_start = wx.Button(parent=self, label=u"立刻开始")
        self.btn_cron = wx.Button(parent=self, label=u"定时开始")
        self.btn_stop = wx.Button(parent=self, label=u"停止")
        self.btn_log = wx.Button(parent=self, label=u"日志")
        self.btn_clear = wx.Button(parent=self, label=u"清除日志")
        img = wx.Image(r'img/xiniu.png', wx.BITMAP_TYPE_ANY).Scale(100, 100)
        self.img = wx.StaticBitmap(self, -1, wx.BitmapFromImage(img))
        self.text.SetEditable(False)
        self.grid = wx.GridBagSizer(5, 5)
        self.grid.Add(self.text, pos=(0, 0), flag=wx.ALL | wx.EXPAND, span=(7, 4), border=5)
        self.grid.Add(self.btn_start, pos=(0, 4), flag=wx.ALL | wx.ALIGN_CENTER, span=(1, 1), border=5)
        self.grid.Add(self.btn_cron, pos=(1, 4), flag=wx.ALL | wx.ALIGN_CENTER, span=(1, 1), border=5)
        self.grid.Add(self.btn_stop, pos=(2, 4), flag=wx.ALL | wx.ALIGN_CENTER, span=(1, 1), border=5)
        self.grid.Add(self.btn_log, pos=(3, 4), flag=wx.ALL | wx.ALIGN_CENTER, span=(1, 1), border=5)
        self.grid.Add(self.btn_clear, pos=(4, 4), flag=wx.ALL | wx.ALIGN_CENTER, span=(1, 1), border=5)
        self.grid.Add(self.img, pos=(5, 4), flag=wx.ALL | wx.ALIGN_CENTER, span=(2, 1), border=5)
        self.SetSizer(self.grid)
        self.grid.AddGrowableCol(0, 1)
        self.grid.AddGrowableCol(1, 1)
        self.grid.AddGrowableCol(2, 1)
        self.grid.AddGrowableCol(3, 1)
        self.grid.AddGrowableCol(4, 1)
        self.grid.AddGrowableRow(0, 1)
        self.grid.AddGrowableRow(1, 1)
        self.grid.AddGrowableRow(2, 1)
        self.grid.AddGrowableRow(3, 1)
        self.grid.AddGrowableRow(4, 1)
        self.grid.AddGrowableRow(5, 1)
        self.grid.Fit(self)
        self.Bind(wx.EVT_BUTTON, self.onStart, self.btn_start)
        self.Bind(wx.EVT_BUTTON, self.onCron, self.btn_cron)
        self.Bind(wx.EVT_BUTTON, self.onStop, self.btn_stop)
        self.Bind(wx.EVT_BUTTON, self.onLog, self.btn_log)
        self.Bind(wx.EVT_BUTTON, self.onClear, self.btn_clear)
        self.timer = None
        handler = MyLogHandler(self.text)
        logging.getLogger('spider').addHandler(handler)
        conf = ConfigParser.ConfigParser()
        with codecs.open('conf.ini', encoding="utf-8-sig" ) as f:
            conf.readfp(f)
            self.max_size = int(conf.get("xiniu_log", "max_size")) * 1024 * 1024
            self.log_path = conf.get("xiniu_log", "path")
            self.cron = conf.get("xiniu_cron", "cron")
    def OnTimerEvent(self, event):
        thread.start_new_thread(self.clear, (event,))
    def clear(self, e):
        if len(self.text.GetValue()) > 1024:
            self.text.Clear()

    def onStart(self, e):
        if self.timer:
            return
        self.btn_start.Disable()
        self.btn_cron.Disable()
        self.btn_stop.Enable()
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimerEvent)
        self.timer.Start(4000)
        thread.start_new_thread(self._run, (e,))

    def onCron(self, e):
        if self.timer:
            return
        self.btn_start.Disable()
        self.btn_cron.Disable()
        self.btn_stop.Enable()
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimerEvent)
        self.timer.Start(4000)
        thread.start_new_thread(self._cron, (e,))

    def onStop(self, e):
        global block_xiniu
        block_xiniu = False
        self.btn_start.Enable()
        self.btn_cron.Enable()
        self.btn_stop.Disable()
        if not self.timer:
            return
        self.timer.Stop()
        self.timer = None
    def _cron(self, e):
        self.btn_start.Disable()
        global block_xiniu
        block_xiniu = True
        while block_xiniu:
            tstr = time.strftime('%H:%M')
            conf = ConfigParser.ConfigParser()
            with codecs.open('conf.ini', encoding="utf-8-sig" ) as f:
                conf.readfp(f)
                cron = conf.get("xiniu_cron", "cron")
            print tstr
            if cron == tstr:
                spider = XiniuSpider()
                spider.run()
                continue
            time.sleep(1)

    def _run(self, e):
        spider = XiniuSpider()
        spider.run()

    def onLog(self, e):
        win32api.ShellExecute(0, 'open', self.log_path, '', '', 1)

    def onClear(self, e):
        with open(self.log_path, 'w') as f:
            f.truncate()

class weibo(wx.Panel):

    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self.panel = wx.Panel

        self.text_weibo = wx.TextCtrl(parent=self, style=wx.TE_AUTO_SCROLL | wx.TE_MULTILINE, size=(600, 500))
        self.btn_start = wx.Button(parent=self, label=u"开始")
        self.btn_stop = wx.Button(parent=self, label=u"停止")
        self.btn_log = wx.Button(parent=self, label=u"日志")
        self.btn_clear = wx.Button(parent=self, label=u"清除日志")
        img = wx.Image(r'img/sina.jpg', wx.BITMAP_TYPE_ANY).Scale(100, 70)
        self.img = wx.StaticBitmap(self, -1, wx.BitmapFromImage(img))

        self.text_weibo.SetEditable(False)
        #布局
        self.grid = wx.GridBagSizer(5, 5)
        self.grid.Add(self.text_weibo, pos=(0, 0), flag=wx.ALL | wx.EXPAND, span=(7, 4), border=5)
        self.grid.Add(self.btn_start, pos=(0, 4), flag=wx.ALL | wx.ALIGN_CENTER, span=(1, 1), border=5)
        self.grid.Add(self.btn_stop, pos=(1, 4), flag=wx.ALL | wx.ALIGN_CENTER, span=(1, 1), border=5)
        self.grid.Add(self.btn_log, pos=(2, 4), flag=wx.ALL | wx.ALIGN_CENTER, span=(1, 1), border=5)
        self.grid.Add(self.btn_clear, pos=(3, 4,), flag=wx.ALL | wx.ALIGN_CENTER, span=(1, 1), border=5)
        self.grid.Add(self.img, pos=(4, 4), flag=wx.ALL | wx.ALIGN_CENTER, span=(2, 1), border=5)
        self.SetSizer(self.grid)
        self.grid.AddGrowableCol(0, 1)
        self.grid.AddGrowableCol(1, 1)
        self.grid.AddGrowableCol(2, 1)
        self.grid.AddGrowableCol(3, 1)
        self.grid.AddGrowableCol(4, 1)
        self.grid.AddGrowableRow(0, 1)
        self.grid.AddGrowableRow(1, 1)
        self.grid.AddGrowableRow(2, 1)
        self.grid.AddGrowableRow(3, 1)
        self.grid.AddGrowableRow(4, 1)
        self.grid.AddGrowableRow(5, 1)
        self.grid.Fit(self)
        #事件绑定
        self.Bind(wx.EVT_BUTTON, self.onStart, self.btn_start)
        self.Bind(wx.EVT_BUTTON, self.onStop, self.btn_stop)
        self.Bind(wx.EVT_BUTTON, self.onLog, self.btn_log)
        self.Bind(wx.EVT_BUTTON, self.onClear, self.btn_clear)
        self.timer = None
        #日志输出到面板
        handler = MyLogHandler(self.text_weibo)
        logging.getLogger('weibo').addHandler(handler)

        #加载配置
        conf = ConfigParser.ConfigParser()
        with codecs.open('conf.ini', encoding="utf-8-sig" ) as f:
            conf.readfp(f)
        #日志单位为M
        self.max_size = int(conf.get("weibo_log", "max_size")) * 1024 * 1024
        self.log_path = conf.get("weibo_log", "path")


    #定时清理显示以及日志
    def OnTimerEvent(self, e):
        thread.start_new_thread(self.clear, (e,))
    def clear(self, e):
        if len(self.text_weibo.GetValue()) > 1024:
            self.text_weibo.Clear()

    #开始按钮
    def onStart(self, e):
        self.btn_start.Disable()
        self.btn_stop.Enable()
        if self.timer:
            return
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimerEvent)
        self.timer.Start(4000)
        thread.start_new_thread(self._run, (e,))
    #暂停
    def onStop(self, e):
        self.btn_start.Enable()
        self.btn_stop.Disable()
        global block_weibo
        block_weibo = False
        if not self.timer:
            return
        self.timer.Stop()
        self.timer = None
    def _run(self, e):
        scan = WeiboScan()
        scan.run()

    def onLog(self, e):
        win32api.ShellExecute(0, 'open', self.log_path, '', '', 1)
    def onClear(self, e):
        with open(self.log_path, 'w') as f:
            f.truncate()

class neeq(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self.text_neeq = wx.TextCtrl(parent=self, style=wx.TE_AUTO_SCROLL | wx.TE_MULTILINE, size=(600, 500))
        self.btn_start = wx.Button(parent=self, label=u"开始")
        self.btn_stop = wx.Button(parent=self, label=u"停止")
        self.btn_log = wx.Button(parent=self, label=u"日志")
        self.btn_clear = wx.Button(parent=self, label=u"清除日志")
        img = wx.Image(r'img/neeq.jpg', wx.BITMAP_TYPE_ANY).Scale(100, 100)
        self.img = wx.StaticBitmap(self, -1, wx.BitmapFromImage(img))
        self.text_neeq.SetEditable(False)
        #布局
        self.grid = wx.GridBagSizer(5, 5)
        self.grid.Add(self.text_neeq, pos=(0, 0), flag=wx.ALL | wx.EXPAND, span=(7, 4), border=5)
        self.grid.Add(self.btn_start, pos=(0, 4), flag=wx.ALL | wx.ALIGN_CENTER, span=(1, 1), border=5)
        self.grid.Add(self.btn_stop, pos=(1, 4), flag=wx.ALL | wx.ALIGN_CENTER, span=(1, 1), border=5)
        self.grid.Add(self.btn_log, pos=(2, 4), flag=wx.ALL | wx.ALIGN_CENTER, span=(1, 1), border=5)
        self.grid.Add(self.btn_clear, pos=(3, 4,), flag=wx.ALL | wx.ALIGN_CENTER, span=(1, 1), border=5)
        self.grid.Add(self.img, pos=(4, 4), flag=wx.ALL | wx.ALIGN_CENTER, span=(2, 1), border=5)
        self.SetSizer(self.grid)
        self.grid.AddGrowableCol(0, 1)
        self.grid.AddGrowableCol(1, 1)
        self.grid.AddGrowableCol(2, 1)
        self.grid.AddGrowableCol(3, 1)
        self.grid.AddGrowableCol(4, 1)
        self.grid.AddGrowableRow(0, 1)
        self.grid.AddGrowableRow(1, 1)
        self.grid.AddGrowableRow(2, 1)
        self.grid.AddGrowableRow(3, 1)
        self.grid.AddGrowableRow(4, 1)
        self.grid.AddGrowableRow(5, 1)
        self.grid.Fit(self)
        #事件绑定
        self.Bind(wx.EVT_BUTTON, self.onStart, self.btn_start)
        self.Bind(wx.EVT_BUTTON, self.onStop, self.btn_stop)
        self.Bind(wx.EVT_BUTTON, self.onLog, self.btn_log)
        self.Bind(wx.EVT_BUTTON, self.onClear, self.btn_clear)
        self.timer = None
        #日志输出到面板
        handler = MyLogHandler(self.text_neeq)
        logging.getLogger('neeq').addHandler(handler)
        #加载配置
        conf = ConfigParser.ConfigParser()
        with codecs.open('conf.ini', encoding="utf-8-sig" ) as f:
            conf.readfp(f)
        #日志单位为M
        self.max_size = int(conf.get("neeq_log", "max_size")) * 1024 * 1024
        self.log_path = conf.get("neeq_log", "path")
    #定时清理显示以及日志
    def OnTimerEvent(self, e):
        thread.start_new_thread(self.clear, (e,))
    def clear(self, e):
        if len(self.text_neeq.GetValue()) > 1024:
            self.text_neeq.Clear()

    #开始按钮
    def onStart(self, e):
        self.btn_start.Disable()
        self.btn_stop.Enable()
        if self.timer:
            return
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimerEvent)
        self.timer.Start(4000)
        thread.start_new_thread(self._run, (e,))

    #暂停
    def onStop(self, e):
        self.btn_start.Enable()
        self.btn_stop.Disable()
        global block_neeq
        block_neeq = False
        if not self.timer:
            return
        self.timer.Stop()
        self.timer = None

    def _run(self, e):
        scan = NeeqNewsScan()
        scan.run()

    def onLog(self, e):
        win32api.ShellExecute(0, 'open', self.log_path, '', '', 1)
    def onClear(self, e):
        with open(self.log_path, 'w') as f:
            f.truncate()

#主体框架
class MainFrame(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, parent=None, title=u"信息监控中心", size=(1100, 700))
        #notebook
        p = wx.Panel(self)
        nb = wx.Notebook(p)
        nb.AddPage(xiniu(nb), u"犀牛之星抓取")
        nb.AddPage(weibo(nb), u"新浪微博更新")
        nb.AddPage(neeq(nb), u"股转新闻更新")
        nb.AddPage(info(nb), u"股转公司公告")

        sizer = wx.BoxSizer()
        sizer.Add(nb, 1, wx.EXPAND)
        p.SetSizer(sizer)
        self.CreateStatusBar()
        filemenu = wx.Menu()
        menuAbout = filemenu.Append(wx.ID_ABOUT, "&About", "Get Help from git@github.com:kuangggg")
        menuExit = filemenu.Append(wx.ID_EXIT, "&Exit", "Terminate the program")
        menuBar = wx.MenuBar()
        helpmenu = wx.Menu()
        menuBar.Append(filemenu, "&File")
        menuBar.Append(helpmenu, "&Help")
        self.SetMenuBar(menuBar)
        self.Bind(wx.EVT_MENU, self.OnAbout, menuAbout)
        self.Bind(wx.EVT_MENU, self.OnExit, menuExit)

        self.toolBar = self.CreateToolBar()
        self.tool_set = self.toolBar.AddSimpleTool(wx.NewId(), wx.Image('img/set.png', wx.BITMAP_TYPE_ANY).Scale(20, 20).ConvertToBitmap(), u"配置", u"配置相关")
        self.toolBar.Realize()
        self.Bind(wx.EVT_TOOL, self.OnSet, self.tool_set)

        self.SetSizeHints(600, 500, 1100, 700)
        self.SetMenuBar(menuBar)
        self.Center()
    def OnAbout(self, e):
        dlg = wx.MessageDialog(self, u"犀牛之星信息采集程序,所有解释权限保留<3bf.cc>.", u"关于我们", wx.OK)
        dlg.ShowModal()
        dlg.Destroy()
    def OnExit(self, e):
        ret = wx.MessageBox('Do you really want to leave?', 'Confirm', wx.OK | wx.CANCEL)
        if ret == wx.OK:
            wx.GetApp().ExitMainLoop()
            e.Skip()

    def OnSet(self, e):
        win32api.ShellExecute(0, 'open', r'conf.ini', '', '', 1)

#入口
if __name__ == '__main__':
    app = wx.App(False)
    MainFrame().Show()
    app.MainLoop()
