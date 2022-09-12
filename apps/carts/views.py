import json
import django_redis
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.views import View
from django_redis import get_redis_connection

# Create your views here.
"""
1.  京东的网址 登录用户可以实现购物车，未登录用户可以实现购物车      v
    淘宝的网址 必须是登录用户才可以实现购物车

2.  登录用户数据保存在哪里？    服务器里       mysql/redis
                                        mysql
                                        redis           学习， 购物车频繁增删改查
                                        mysql+redis
    未登录用户数据保存在哪里？   客户端
                                        cookie      

3.  保存哪些数据？？？

    redis:
            user_id,sku_id(商品id),count(数量),selected（选中状态）

    cookie:
            sku_id,count,selected,

4.  数据的组织

    redis:
            user_id,    sku_id(商品id),count(数量),selected（选中状态）

            hash
            user_id:
                    sku_id:count
                    xxx_sku_id:selected

            1：  
                    1:10
                    xx_1: True

                    2:20
                    xx_2: False

                    3:30
                    xx_3: True
            13个地方的空间

            进一步优化！！！
            为什么要优化呢？？？
            redis的数据保存在 内存中  我们应该尽量少的占用redis的空间

            user_id:
                    sku_id:count


            selected 



            user_1:         id:数量
                            1: 10 
                            2: 20
                            3: 30
            记录选中的商品
            1,3



            user_1
                    1: 10 
                    2: 20
                    3: 30
            selected_1: {1,3}

            10个空间


             user_1
                    1: 10 
                    2: -20
                    3: 30

            7个空间

    cookie:
        {
            sku_id: {count:xxx,selected:xxxx},
            sku_id: {count:xxx,selected:xxxx},
            sku_id: {count:xxx,selected:xxxx},
        }


5.
    cookie字典转换为字符串保存起来，数据没有加密


    base64：         6个比特位为一个单元

    1G=1024MB
    1MB=1024KB
    1KB=1024B

    1B=8bytes

    bytes 0 或者 1

    ASCII

    a 
    0110 0001

    a               a       a                   24比特位
    0110 0001  0110 0001   0110 0001 

    011000      010110      000101          100001 
    X               Y       Z                  N

    aaa --> XYZN

    base64模块使用：
        base64.b64encode()将bytes类型数据进行base64编码，返回编码后的bytes类型数据。
        base64.b64deocde()将base64编码后的bytes类型数据进行解码，返回解码后的bytes类型数据。



    字典 ----》 pickle ------二进制------》Base64编码

    pickle模块使用：
        pickle.dumps()将Python数据序列化为bytes类型数据。
        pickle.loads()将bytes类型数据反序列化为python数据。

#######################编码数据####################################
# 字典
carts = {
    '1': {'count':10,'selected':True},
    '2': {'count':20,'selected':False},
}


# 字典转换为 bytes类型
import pickle
b=pickle.dumps(carts)

# 对bytes类型的数据进行base64编码
import base64
encode=base64.b64encode(b)
#######################解码数据####################################

# 将base64编码的数据解码
decode_bytes=base64.b64decode(encode)

# 再对解码的数据转换为字典
pickle.loads(decode_bytes)

6.
请求
业务逻辑（数据的增删改查）
响应


增 （注册）
    1.接收数据
    2.验证数据
    3.数据入库
    4.返回响应

删 
    1.查询到指定记录
    2.删除数据（物理删除，逻辑删除）
    3.返回响应

改  （个人的邮箱）
    1.查询指定的记录
    2.接收数据
    3.验证数据
    4.数据更新
    5.返回响应

查   （个人中心的数据展示，省市区）
    1.查询指定数据
    2.将对象数据转换为字典数据
    3.返回响应

"""
from apps.goods.models import SKU
import pickle
import base64

"""
前端：
    我们点击添加购物车之后， 前端将 商品id ，数量 发送给后端

后端：
    请求：         接收参数，验证参数
    业务逻辑：       根据商品id查询数据库看看商品id对不对
                  数据入库
                    登录用户入redis
                        连接redis
                        获取用户id
                        hash
                        set
                        返回响应
                    未登录用户入cookie
                        先有cookie字典
                        字典转换为bytes
                        bytes类型数据base64编码
                        设置cookie
                        返回响应
    响应：         返回JSON
    路由：     POST  /carts/
    步骤：
            1.接收数据
            2.验证数据
            3.判断用户的登录状态
            4.登录用户保存redis
                4.1 连接redis
                4.2 操作hash
                4.3 操作set
                4.4 返回响应
            5.未登录用户保存cookie
                5.1 先有cookie字典
                5.2 字典转换为bytes
                5.3 bytes类型数据base64编码
                5.4 设置cookie
                5.5 返回响应
"""


class CartsView(View):
    def post(self, request):
        # 1.接收数据
        data = json.loads(request.body)
        sku_id = data.get('sku_id')
        count = data.get('count')
        # 2.验证数据
        try:
            sku = SKU.objects.get(id=sku_id)
        except SKU.DoesNotExist:
            return JsonResponse({'code': 400, 'errmsg': '查无此商品'})
        # 类型强制转换
        try:
            count = int(count)
        except Exception:
            count = 1
        # 3.判断用户的登录状态
        # request.user 如果是登录用户，就是 关联User的模型数据
        # is_authenticated = True 认证用户
        # 如果不是登录用户，就是匿名用户
        # 匿名用户的 is_authenticated = False
        #
        user = request.user
        if user.is_authenticated:
            # 4.登录用户保存redis
            #     4.1 连接redis
            redis_cli = get_redis_connection('carts')
            pipeline = redis_cli.pipeline()
            #     4.2 操作hash
            # redis_cli.hset(keys,field,value)
            # 1. 先获取之前的数据，然后累加
            # 2.
            # redis_cli.hset('carts_%s'%user.id,sku_id,count)
            # hincrby
            # 会进行累加操作
            pipeline.hincrby('carts_%s' % user.id, sku_id, count)
            #     4.3 操作set
            # 默认就是选中
            pipeline.sadd('selected_%s' % user.id, sku_id)

            # 一定要执行！！！
            pipeline.execute()
            #     4.4 返回响应
            return JsonResponse({'code': 0, 'errmsg': 'ok'})
        else:
            # 5.未登录用户保存cookie
            """

                cookie:
                    {
                        sku_id: {count:xxx,selected:xxxx},
                        sku_id: {count:xxx,selected:xxxx},
                        sku_id: {count:xxx,selected:xxxx},
                    }

            """
            # {16： {count:3,selected:True}}

            # 5.0 先读取cookie数据
            cookie_carts = request.COOKIES.get('carts')
            if cookie_carts:
                # 对加密的数据解密
                carts = pickle.loads(base64.b64decode(cookie_carts))
            else:
                #     5.1 先有cookie字典
                carts = {}

            # 判断新增的商品 有没有在购物车里
            if sku_id in carts:
                # 购物车中 已经有该商品id
                # 数量累加
                ## {16： {count:3,selected:True}}
                origin_count = carts[sku_id]['count']
                count += origin_count

            #     carts[sku_id] = {
            #         'count':count,
            #         'selected':True
            #     }
            # else:
            # 购物车中 没有该商品id
            # {16： {count:3,selected:True}}
            carts[sku_id] = {
                'count': count,
                'selected': True
            }

            #     5.2 字典转换为bytes
            carts_bytes = pickle.dumps(carts)
            #     5.3 bytes类型数据base64编码
            base64encode = base64.b64encode(carts_bytes)
            #     5.4 设置cookie
            response = JsonResponse({'code': 0, 'errmsg': 'ok'})
            # keys, value='', max_age=None
            # base64encode.decode() 的作用是 将bytes类型转换为 str
            # 因为 value的数据是 str数据
            response.set_cookie('carts', base64encode.decode(), max_age=3600 * 24 * 12)
            #     5.5 返回响应
            return response

    """
    1.判断用户是否登录
    2.登录用户查询redis
        2.1 连接redis
        2.2 hash        {sku_id:count}
        2.3 set         {sku_id}
        2.4 遍历判断
        2.5 根据商品商品id查询商品信息
        2.6 将对象数据转换为字典数据
        2.7 返回响应
    3.未登录用户查询cookie
        3.1 读取cookie数据
        3.2 判断是否存在购物车数据
            如果存在，则解码            {sku_id:{count:xxx,selected:xxx}}
            如果不存在，初始化空字典
        3.3 根据商品id查询商品信息
        3.4 将对象数据转换为字典数据
        3.5 返回响应


    1.判断用户是否登录
    2.登录用户查询redis
        2.1 连接redis
        2.2 hash        {sku_id:count}
        2.3 set         {sku_id}
        2.4 遍历判断
    3.未登录用户查询cookie
        3.1 读取cookie数据
        3.2 判断是否存在购物车数据
            如果存在，则解码            {sku_id:{count:xxx,selected:xxx}}
            如果不存在，初始化空字典

    4 根据商品id查询商品信息
    5 将对象数据转换为字典数据
    6 返回响应

    """

    def get(self, request):
        # 1.判断用户是否登录
        user = request.user
        # carts = {}

        # 2.登录用户查询redis
        if user.is_authenticated:
            #     2.1 连接redis
            redis_cli = get_redis_connection('carts')
            #     2.2 hash        {sku_id:count} {2:count,3:count,...}
            sku_id_count = redis_cli.hgetall('carts_%s' % user.id)
            #     2.3 set         {sku_id} {2}
            selected_ids = redis_cli.smembers('selected_%s' % user.id)
            #     2.4 将 redis的数据转换为 和 cookie一样
            #    这样就可以在后续操作的时候 统一操作
            # {sku_id:{count:xxx,selected:xxx}}
            carts = {}
            for sku_id, count in sku_id_count.items():
                carts[int(sku_id)] = {
                    'count': int(count),
                    'selected': sku_id in selected_ids
                }
        else:
            # 3.未登录用户查询cookie
            #     3.1 读取cookie数据
            cookie_cart = request.COOKIES.get('carts')
            #     3.2 判断是否存在购物车数据
            if cookie_cart is not None:
                #         如果存在，则解码            {sku_id:{count:xxx,selected:xxx}}
                cart_code = base64.b64decode(cookie_cart)
                carts = pickle.loads(cart_code)
            else:
                #         如果不存在，初始化空字典
                carts = {}
        # {sku_id: {count: xxx, selected: xxx}}
        # 4 根据商品id查询商品信息
        # 可以直接遍历 carts
        # 也可以获取 字典的最外层的key，最外层的所有key就是商品id
        sku_ids = carts.keys()
        # [1,2,3,4,5]
        # 可以遍历查询
        # 也可以用 in
        skus = SKU.objects.filter(id__in=sku_ids)

        sku_list = []
        for sku in skus:
            # 5 将对象数据转换为字典数据
            sku_list.append({
                'id': sku.id,
                'price': sku.price,
                'name': sku.name,
                'default_image_url': sku.default_image.url,
                'selected': carts[sku.id]['selected'],  # 选中状态
                'count': int(carts[sku.id]['count']),  # 数量 强制转换一下
                'amount': sku.price * carts[sku.id]['count']  # 总价格
            })

        # 6 返回响应
        return JsonResponse({'code': 0, 'errmsg': 'ok', 'cart_skus': sku_list})

    """
    1.获取用户信息
    2.接收数据
    3.验证数据
    4.登录用户更新redis
        4.1 连接redis
        4.2 hash
        4.3 set
        4.4 返回响应
    5.未登录用户更新cookie
        5.1 先读取购物车数据
            判断有没有。
            如果有则解密数据
            如果没有则初始化一个空字典
        5.2 更新数据
        5.3 重新最字典进行编码和base64加密
        5.4 设置cookie
        5.5 返回响应
    """

    def put(self, request):
        # 1.获取用户信息
        user = request.user
        # 2.接收数据
        data = json.loads(request.body.decode())
        sku_id = data.get('sku_id')
        count = data.get('count')
        selected = data.get('selected')
        # 3.验证数据
        if not all([sku_id, count]):
            return JsonResponse({'code': 400, 'errmsg': '参数不全'})

        try:
            SKU.objects.get(id=sku_id)
        except SKU.DoesNotExist:
            return JsonResponse({'code': 400, 'errmsg': '没有此商品'})

        try:
            count = int(count)
        except Exception:
            count = 1

        if user.is_authenticated:
            # 4.登录用户更新redis
            #     4.1 连接redis
            redis_cli = get_redis_connection('carts')
            #     4.2 hash
            redis_cli.hset('carts_%s' % user.id, sku_id, count)
            #     4.3 set
            if selected:
                redis_cli.sadd('selected_%s' % user.id, sku_id)
            else:
                redis_cli.srem('selected_%s' % user.id, sku_id)
            #     4.4 返回响应
            return JsonResponse({'code': 0, 'errmsg': 'ok', 'cart_sku': {'count': count, 'selected': selected}})

        else:
            # 5.未登录用户更新cookie
            #     5.1 先读取购物车数据
            cookie_cart = request.COOKIES.get('carts')
            #         判断有没有。
            if cookie_cart is not None:
                #         如果有则解密数据
                carts = pickle.loads(base64.b64decode(cookie_cart))
            else:
                #         如果没有则初始化一个空字典
                carts = {}

            #     5.2 更新数据
            # {sku_id: {count:xxx,selected:xxx}}
            if sku_id in carts:
                carts[sku_id] = {
                    'count': count,
                    'selected': selected
                }
            #     5.3 重新最字典进行编码和base64加密
            new_carts = base64.b64encode(pickle.dumps(carts))
            #     5.4 设置cookie
            response = JsonResponse({'code': 0, 'errmsg': 'ok', 'cart_sku': {'count': count, 'selected': selected}})
            response.set_cookie('carts', new_carts.decode(), max_age=14 * 24 * 3600)
            #     5.5 返回响应
            return response

    """
    1.接收请求
    2.验证参数
    3.根据用户状态
    4.登录用户操作redis
        4.1 连接redis
        4.2 hash
        4.3 set
        4.4 返回响应
    5.未登录用户操作cookie
        5.1 读取cookie中的购物车数据
        判断数据是否存在
        存在则解码
        不存在则初始化字典
        5.2 删除数据 {}
        5.3 我们需要对字典数据进行编码和base64的处理
        5.4 设置cookie
        5.5 返回响应

    """

    def delete(self, request):
        # 1.接收请求
        data = json.loads(request.body.decode())
        # 2.验证参数
        sku_id = data.get('sku_id')
        try:
            SKU.objects.get(pk=sku_id)  # pk primary keys
        except SKU.DoesNotExist:
            return JsonResponse({'code': 400, 'errmsg': '没有此商品'})
        # 3.根据用户状态
        user = request.user
        if user.is_authenticated:

            # 4.登录用户操作redis
            #     4.1 连接redis
            redis_cli = get_redis_connection('carts')
            #     4.2 hash
            redis_cli.hdel('carts_%s' % user.id, sku_id)
            #     4.3 set
            redis_cli.srem('selected_%s' % user.id, sku_id)
            #     4.4 返回响应
            return JsonResponse({'code': 0, 'errmsg': 'ok'})

        else:
            # 5.未登录用户操作cookie
            #     5.1 读取cookie中的购物车数据
            cookie_cart = request.COOKIES.get('carts')
            #     判断数据是否存在
            if cookie_cart is not None:
                #     存在则解码
                carts = pickle.loads(base64.b64decode(cookie_cart))
            else:
                #     不存在则初始化字典
                carts = {}
            #     5.2 删除数据 {}
            del carts[sku_id]
            #     5.3 我们需要对字典数据进行编码和base64的处理
            new_carts = base64.b64encode(pickle.dumps(carts))
            #     5.4 设置cookie
            response = JsonResponse({'code': 0, 'errmsg': 'ok'})
            response.set_cookie('carts', new_carts.decode(), max_age=14 * 24 * 3600)
            #     5.5 返回响应
            return response


class CartsSelectAllView(View):
    """全选购物车"""

    def put(self, request):
        # 接收参数
        json_dict = json.loads(request.body)
        selected = json_dict.get('selected', True)

        # 校验参数
        if selected:
            if not isinstance(selected, bool):
                return HttpResponseBadRequest('参数selected有误')

        # 判断用户是否登录
        user = request.user
        if user is not None and user.is_authenticated:
            # 用户已登录，操作redis购物车
            redis_conn = get_redis_connection('carts')
            cart = redis_conn.hgetall('carts_%s' % user.id)
            sku_id_list = cart.keys()
            if selected:
                # 全选
                redis_conn.sadd('selected_%s' % user.id, *sku_id_list)
            else:
                # 取消全选
                redis_conn.srem('selected_%s' % user.id, *sku_id_list)
            return JsonResponse({'code': 0, 'errmsg': '全选购物车成功'})
        else:
            # 用户未登录，操作cookie购物车
            cart = request.COOKIES.get('carts')
            response = JsonResponse({'code': 0, 'errmsg': '全选购物车成功'})
            if cart is not None:
                cart = pickle.loads(base64.b64decode(cart.encode()))
                for sku_id in cart:
                    cart[sku_id]['selected'] = selected
                cookie_cart = base64.b64encode(pickle.dumps(cart)).decode()
                response.set_cookie('carts', cookie_cart, max_age=7 * 24 * 3600)

            return response


class CartsSimpleView(View):
    """商品页面右上角购物车"""

    def get(self, request):
        # 判断用户是否登录
        user = request.user
        if user.is_authenticated:
            # 用户已登录，查询Redis购物车
            redis_conn = get_redis_connection('carts')
            redis_cart = redis_conn.hgetall('carts_%s' % user.id)
            cart_selected = redis_conn.smembers('selected_%s' % user.id)
            # 将redis中的两个数据统一格式，跟cookie中的格式一致，方便统一查询
            cart_dict = {}
            for sku_id, count in redis_cart.items():
                cart_dict[int(sku_id)] = {
                    'count': int(count),
                    'selected': sku_id in cart_selected
                }
        else:
            # 用户未登录，查询cookie购物车
            cart_str = request.COOKIES.get('carts')
            if cart_str:
                cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))
            else:
                cart_dict = {}

        # 构造简单购物车JSON数据
        cart_skus = []
        sku_ids = cart_dict.keys()
        skus = SKU.objects.filter(id__in=sku_ids)
        for sku in skus:
            cart_skus.append({
                'id': sku.id,
                'name': sku.name,
                'count': cart_dict.get(sku.id).get('count'),
                'default_image_url': sku.default_image.url
            })

        # 响应json列表数据
        return JsonResponse({'code': 0, 'errmsg': 'OK', 'cart_skus': cart_skus})
