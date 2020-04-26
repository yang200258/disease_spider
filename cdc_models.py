from peewee import *

db = MySQLDatabase("spider", host="127.0.0.1", port=3306, user="root", password="Yy141025")


class BaseModel(Model):
    class Meta:
        database = db


class t_article(BaseModel):
    article_id = UUIDField(primary_key=True)
    category_name = CharField()
    title = CharField()
    keyword = CharField()
    symptom = CharField()
    content = TextField()
    source = CharField()
    article_state = FixedCharField(default='0')
    check_option = CharField()
    createtime = DateField()   #创建
    create_user_id = CharField()
    create_user_name = CharField()
    update_time = DateTimeField()   #更新
    update_user_id = CharField()
    update_user_name = CharField()
    note = CharField()   # 文章url
    data_source_code = CharField()  #数据来源
    data_source_name = CharField()
    is_active = CharField()   #是否有效


class t_category(BaseModel):
    category_id = UUIDField(primary_key=True)
    category_name = CharField()
    parent_id = CharField()
    level = IntegerField()
    level_code = UUIDField()
    create_time = DateTimeField()
    create_user_id = CharField()
    create_user_name = CharField()
    update_time = DateTimeField()  # 更新
    update_user_id = CharField()
    update_user_name = CharField()
    note = CharField()
    organization_name = CharField()


if __name__ == "__main__":
    db.create_tables([t_article, t_category])
