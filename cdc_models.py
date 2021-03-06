from peewee import *

db = MySQLDatabase("xxcj", host="59.212.39.6", port=3306, user="jikong", password="Zh~m,nhG!3")
# db_formal = MySQLDatabase("spider", host="127.0.0.1", port=3306, user="root", password="root")


class BaseModelTest(Model):
    class Meta:
        database = db


# class BaseModelFormal(Model):
#     class Meta:
#         database = db_formal


class t_article(BaseModelTest):
    article_id = UUIDField(primary_key=True)
    category_name = CharField()
    title = CharField()
    keyword = CharField(default=None)
    symptom = CharField(default=None)
    content = TextField()
    source = CharField()
    article_state = FixedCharField(default='0')
    CHECK_OPINION = CharField(default=None)
    create_time = DateField()   #创建
    create_user_id = CharField()
    create_user_name = CharField()
    update_time = DateTimeField()   #更新
    update_user_id = CharField()
    update_user_name = CharField()
    note = CharField()   # 文章url
    data_source_code = CharField()  #数据来源
    data_source_name = CharField()
    is_active = CharField()   #是否有效


class t_category(BaseModelTest):
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
    ORGANIZATION_NAME = CharField(default=None)


class t_article_category(BaseModelTest):
    article_id = UUIDField()
    category_id = UUIDField()


if __name__ == "__main__":
    db.create_tables([ t_category])
    # db_formal.create_tables([t_article_test, t_category_test])
