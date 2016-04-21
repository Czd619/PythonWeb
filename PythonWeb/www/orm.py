__author__ = 'chen'
import aiomysql		# �첽mysql����֧��
import logging		# ֧����־����
import asyncio
import pdb


def log(sql, args=()):
    # �ú������ڴ�ӡִ�е�SQL���
    logging.info('SQL:%s' % sql)


@asyncio.coroutine
def create_pool(loop, **kw):		# ����ؼ��ֺ�����ʾimport asyncio��
    # �ú������ڴ������ӳ�
    global __pool  # ȫ�ֱ������ڱ������ӳ�
    __pool = yield from aiomysql.create_pool(
        host=kw.get('host', 'localhost'),  # Ĭ�϶���host����Ϊlocalhost
        port=kw.get('port', 3306),		# Ĭ�϶���mysql��Ĭ�϶˿���3306
        user=kw['user'],				# user��ͨ���ؼ��ֲ�����������
        password=kw['password'],		# ����Ҳ��ͨ���ؼ��ֲ�����������
        db=kw['database'],                   # ���ݿ����֣������ORM���Ե�ʹ����ʹ��db=kw['db']
        charset=kw.get('charset', 'utf8'),  # Ĭ�����ݿ��ַ�����utf8
        autocommit=kw.get('autocommit', True),  # Ĭ���Զ��ύ����
        maxsize=kw.get('maxsize', 10),		# ���ӳ����ͬʱ����10������
        minsize=kw.get('minsize', 1),		# ���ӳ�����1������
        loop=loop		# ������Ϣѭ������loop�����첽ִ��
    )


# =============================SQL��������==========================
# select��execute������ʵ������Model����SQL��䶼����Ҫ�õķ�����ԭ����ȫ�ֺ�����������Ϊ��̬��������
# ע�⣺֮���Է���Model��������Ϊ��̬����������Ϊ�˸��õĹ����ھۣ�����ά�������������ʦ�Ĵ���ʽ��ͬ����ע��


@asyncio.coroutine
def select(sql, args, size=None):
    # select������Ӧ��select����,����sql���Ͳ���
    log(sql, args)
    global __pool  # ��������global,��Ϊ�����ָ�ֵ��ͬ���ľֲ�����(������ʵ����ʡ�ԣ���Ϊ����û��ֵ)

    # with����÷����Բο��ҵĲ��ͣ�http://kaimingwan.com/post/python/pythonzhong-de-withyu-ju-shi-yong

    # �첽�ȴ����ӳض��󷵻ؿ��������̣߳�with������װ�������ر�conn���ʹ����쳣�Ĺ���
    with (yield from __pool) as conn:
        # �ȴ����Ӷ��󷵻�DictCursor����ͨ��dict�ķ�ʽ��ȡ���ݿ������Ҫͨ���α����ִ��SQL
        cur = yield from conn.cursor(aiomysql.DictCursor)
        # ����args��ͨ��repalce������ռλ���滻��%s
        # args��execute�����Ĳ���
        yield from cur.execute(sql.replace('?', '%s'), args or ())
        # pdb.set_trace()
        if size:  # ���ָ��Ҫ���ؼ���
            rs = yield from cur.fetchmany(size)  # �����ݿ��ȡָ��������
        else:       # ���ûָ�����ؼ��У���size=None
            rs = yield from cur.fetchall()  # �������н����
        yield from cur.close()  # ��Ҫ�첽ִ��
        logging.info('rows returned: %s' % len(rs))  # ���LOG��Ϣ
        return rs       # ���ؽ����


@asyncio.coroutine
def execute(sql, args, autocommit=True):
    # execute����ֻ���ؽ�����������ؽ����,����insert,update��ЩSQL���
    log(sql)
    with (yield from __pool) as conn:
        if not autocommit:
            yield from conn.begin()
        try:
            cur = yield from conn.cursor()
            # ִ��sql��䣬ͬʱ�滻ռλ��
            # pdb.set_trace()
            yield from cur.execute(sql.replace('?', '%s'), args)
            affected = cur.rowcount     # ������Ӱ�������
            yield from cur.close()       # �ر��α�
            if not autocommit:
                yield from conn.commit()
        except BaseException as e:
            if not autocommit:
                yield from conn.rollback()
            raise e  # raise������������Ѵ˴��Ĵ���������;Ϊ�˷�����⻹�ǽ����e��
        return affected


# ========================================Model�����Լ�����Ԫ��=====================
# ����͹�ϵ֮��Ҫӳ�����������ȿ��Ǵ�������Model���һ�����࣬�����Model���󣨾������ݿ����������ж�Ӧ�Ķ����ټ̳��������


class ModelMetaclass(type):
    # ��Ԫ����Ҫʹ��Model����߱����¹���:
    # 1.�κμ̳���Model���ࣨ����User�������Զ�ͨ��ModelMetaclassɨ��ӳ���ϵ
    # ���洢���������������__table__��__mappings__��
    # 2.������һЩĬ�ϵ�SQL���

    def __new__(cls, name, bases, attrs):
        # �ų�Model�������
        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)
        # ��ȡtable����,һ�����Model�������:
        tableName = attrs.get('__table__', None) or name 	# ǰ��getʧ���˾�ֱ�Ӹ�ֵname
        logging.info('found model:%s (table:%s)' % (name, tableName))
        # ��ȡ���е�Field��������
        mappings = dict() 		# �������Ժ�ֵ��k,v��
        fields = []				# ����Model�������
        primaryKey = None 		# ����Model�������
        for k, v in attrs.items():
            if isinstance(v, Field):  # �����Field���͵������mappings����
                logging.info('found mapping: %s ==> %s' % (k, v))
                mappings[k] = v
                # k,v��ֵ��ȫ�����浽mappings�У����������ͷ�������
                if v.primary_key:  # ���v��������primary_key=True�����԰��丳ֵ��primaryKey����
                    if primaryKey:  # ���primaryKey�����Ѿ���Ϊ���ˣ�˵���Ѿ��������ˣ����׳�����,��Ϊֻ��1������
                        raise RuntimeError(
                            'Duplicate primary key for field: %s' % k)
                    primaryKey = k 		# ���������û����ֵ������ֱ�Ӹ�ֵ
                else:  # v������������primary_key=False�����
                    fields.append(k)  # ������ȫ���ŵ�fields�б���

        if not primaryKey:  # ��������껹û�ҵ����������׳�����
            raise RuntimeError('Priamry key not found.')

        for k in mappings.keys():  # ���mappings����ֹʵ�����Ը������ͬ�����ԣ��������ʱ����
            # attrs�ж�Ӧ����������Ҫɾ��������ָ����attrs�����Ժ�mappings�е����Է�����ͻ������ԭ�������Ҫ�Լ�ʵ����������������֪��
            attrs.pop(k)

        # %sռλ��ȫ���滻�ɾ����������
        escaped_fields = list(map(lambda f: r"`%s`" % f, fields))

        # ===========��ʼ��˽��˽�е��ر�����===========
        attrs['__mappings__'] = mappings  # �������Ժ��еĹ�ϵ,��ֵ�����������__mappings__
        attrs['__table__'] = tableName
        attrs['__primary_key__'] = primaryKey
        attrs['__fields__'] = fields

        # ===========����Ĭ�ϵ�select,insert,update,delete���=======
        # �����˵����`����mysql����ᱨ������֤
        # Ĭ�ϵ�select���ò��û��ô���õ����Ҹо�ͨ����������ã������粻�Ӱɡ������findAll�����õ���
        attrs['__select__'] = "select `%s`,%s from `%s`" % (
            primaryKey, ','.join(escaped_fields), tableName)
        # insert���ǰ����3��ռλ�������Դӵ��ĸ�%��ʼӦ����(�����滻��һ��%��ֵa1���滻�ڶ���%��ֵa2���滻������%��ֵa3)
        # Ĭ����ִ�е�Ӧ����update tableName set ����1=��������2=����... where ����=primray_key
        # a1��tableNameû���⣬a2Ӧ�������������ԣ�a3��ͨ�������������map��%s=?ȫ���滻��������=��
        # �������������������ǽ�%s���ռλ���滻��`������`=?
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ', '.join(
            map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (
            tableName, primaryKey)
        # ������ռλ���кܶ��ʺţ�Ϊ�˷����ֱ��ʹ����create_ars_string����������num��ռλ����string
        # pdb.set_trace()
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ', '.join(
            escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
        return type.__new__(cls, name, bases, attrs)


def create_args_string(num):    # ��ModelMetaclass������������õ�

    # insert��������ʱ������num��������ռλ��'?'
    L = []
    for n in range(num):
        L.append('?')
    return ', '.join(L)


class Model(dict, metaclass=ModelMetaclass):
    # �̳�dict��Ϊ��ʹ�÷��㣬�������ʵ��user['id']��������ͨ��UserModelȥ���ݿ��ȡ��id
    # Ԫ����Ȼ��Ϊ�˷�װ����֮ǰд�ľ����SQL�������������ݿ��ȡ����

    def __init__(self, **kw):
        # ����dict�ĸ���__init__�������ڴ���Model,super(�����������)
        super(Model, self).__init__(**kw)

    def __getattr__(self, key):
        # ���ò����ڵ�����ʱ����һЩ����
        try:
            return self[key]  # �����������������
        except KeyError:
            raise AttributeError(
                r"'Model' object has no attribute '%s'" % key)		# r��ʾ��ת��

    def __setattr__(self, key, value):
        # �趨Model�����key-value��������value����ΪNone
        self[key] = value

    def getValue(self, key):
        # ��ȡĳ�������ֵ���϶����ڵ������ʹ�øú���,�����ʹ��__getattr()__
        # ��ȡʵ����key��None��Ĭ��ֵ��getattr����ʹ�ÿ��Բο�http://kaimingwan.com/post/python/pythonzhong-de-nei-zhi-han-shu-getattr-yu-fan-she
        return getattr(self, key, None)

    def getValueOrDefault(self, key):
        # ���������valueΪNone��ʱ���ܹ�����Ĭ��ֵ
        value = getattr(self, key, None)
        if value is None:		# ������������ֵ��ֱ�ӷ���
            # self.__mapping__��metaclass�У����ڱ��治ͬʵ��������Model�����е�ӳ���ϵ
            field = self.__mappings__[key]
            if field.default is not None:  # ���ʵ���������Ĭ��ֵ����ʹ��Ĭ��ֵ
                # field.default��callable�Ļ���ֱ�ӵ���
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s:%s' %
                              (key, str(value)))
                setattr(self, key, value)
        return value


# --------------------------ÿ��Model�������ʵ��Ӧ�þ߱���ִ��SQL�ķ�������save------
    @classmethod    # �෽��
    @asyncio.coroutine
    def findAll(cls, where=None, args=None, **kw):
        sql = [cls.__select__]  # ��ȡĬ�ϵ�select���
        if where:   # �����where��䣬���޸�sql����
            # ���ﲻ��Э�̣�����Ϊ����Ҫ�ȴ����ݷ���
            sql.append('where')  # sql�������where�ؼ���
            sql.append(where)   # �����whereʵ������colName='xxx'�������������ʽ
        if args is None:    # ʲô����?
            args = []

        orderBy = kw.get('orderBy', None)    # ��kw�в鿴�Ƿ���orderBy����
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)

        limit = kw.get('limit', None)    # mysql�п���ʹ��limit�ؼ���
        if limit is not None:
            sql.append('limit')
            if isinstance(limit, int):   # �����int����������ռλ��
                sql.append('?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:   # limit����ȡ2����������ʾһ����Χ
                sql.append('?,?')
                args.extend(limit)
            else:       # ���������Ȼ���﷨����
                raise ValueError('Invalid limit value: %s' % str(limit))
            # ��ԭ��Ĭ��SQL�������������䣬Ҫ�Ӹ��ո�

        rs = yield from select(' '.join(sql), args)
        return [cls(**r) for r in rs]   # ���ؽ���������list���������Ԫ����dict���͵�

    @classmethod
    @asyncio.coroutine
    def findNumber(cls, selectField, where=None, args=None):
        # ��ȡ����
        # ����� _num_ ʲô��˼�������� �ҹ�����mysql����һ����¼ʵʱ��ѯ��������ı���
        sql = ['select %s _num_ from `%s`' % (selectField, cls.__table__)]
        # pdb.set_trace()
        if where:
            sql.append('where')
            sql.append(where)   # ���ﲻ�ӿո�
        rs = yield from select(' '.join(sql), args, 1)  # size = 1
        if len(rs) == 0:  # �����Ϊ0�����
            return None
        return rs[0]['_num_']   # �н����rs���list�е�һ���ʵ�Ԫ��_num_���key��valueֵ

    @classmethod
    @asyncio.coroutine
    def find(cls, pk):
        # ������������
        # pk��dict����
        rs = yield from select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])

    # �����ʵ������
    @asyncio.coroutine
    def save(self):
        # arg�Ǳ�������Modelʵ�����Ժ�������list,ʹ��getValueOrDefault�����ĺô��Ǳ���Ĭ��ֵ
        # ���Լ���fields�����ȥ
        args = list(map(self.getValueOrDefault, self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        # pdb.set_trace()
        rows = yield from execute(self.__insert__, args)  # ʹ��Ĭ�ϲ��뺯��
        if rows != 1:
            # ����ʧ�ܾ���rows!=1
            logging.warn(
                'failed to insert record: affected rows: %s' % rows)

    @asyncio.coroutine
    def update(self):
        # ����ʹ��getValue˵��ֻ�ܸ�����Щ�Ѿ����ڵ�ֵ����˲���ʹ��getValueOrDefault����
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        # pdb.set_trace()
        rows = yield from execute(self.__update__, args)    # args�����Ե�list
        if rows != 1:
            logging.warn(
                'failed to update by primary key: affected rows: %s' % rows)

    @asyncio.coroutine
    def remove(self):
        args = [self.getValue(self.__primary_key__)]
        # pdb.set_trace()
        rows = yield from execute(self.__delete__, args)
        if rows != 1:
            logging.warn(
                'failed to remove by primary key: affected rows: %s' % rows)
# =====================================������===============================


class Field(object):  # ���ԵĻ��࣬����������Model��̳�

    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default 			# �������default����getValueOrDefault�лᱻ�õ�

    def __str__(self):  # ֱ��print��ʱ���������ϢΪ�����������ͺ�����
        return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)


class StringField(Field):

    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
        # Stringһ�㲻��Ϊ����������Ĭ��False,DDL�����ݶ������ԣ�Ϊ�����mysql������Ĭ���趨Ϊ100�ĳ���
        super().__init__(name, ddl, primary_key, default)


class BooleanField(Field):

    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)


class IntegerField(Field):

    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'biginit', primary_key, default)


class FloatField(Field):

    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)


class TextField(Field):

    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)  # ����ǲ�����Ϊ�����Ķ�����������ֱ�Ӿ��趨��False��