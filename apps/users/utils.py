from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from mieShop import settings


def generic_email_verify_token(user_id):
    # 1. 创建实例
    s = Serializer(secret_key=settings.SECRET_KEY, expires_in=3600 * 24)
    # 2. 加密数据
    data = s.dumps({'user_id': user_id})
    # 3. 返回数据
    return data.decode()


def check_verify_token(token):
    # 1. 创建实例
    s = Serializer(secret_key=settings.SECRET_KEY, expires_in=3600 * 24)
    # 2. 加密数据---可能有异常
    try:

        data = s.loads(token)
    except Exception:
        return None
    # 3. 返回数据
    return data.get('user_id')
