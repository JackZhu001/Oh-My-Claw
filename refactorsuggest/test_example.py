"""
示例代码 - 包含各种代码异味，用于测试 RefactorSuggest
"""


def very_long_function_with_many_lines_and_high_complexity(x, y, z, a, b, c):
    """
    这是一个过长的函数，用于测试工具的检测能力
    """
    result = 0
    
    # 第一部分
    if x > 0:
        if y > 0:
            if z > 0:
                result = x + y + z
            else:
                result = x + y
        else:
            if z > 0:
                result = x + z
            else:
                result = x
    else:
        if y > 0:
            if z > 0:
                result = y + z
            else:
                result = y
        else:
            if z > 0:
                result = z
            else:
                result = 0
    
    # 第二部分
    for i in range(10):
        for j in range(10):
            if i > 5:
                if j > 5:
                    result += i * j
                else:
                    result += i
            else:
                if j > 5:
                    result += j
                else:
                    result += 1
    
    # 第三部分
    try:
        result = result / a
    except ZeroDivisionError:
        result = 0
    finally:
        result += 1
    
    # 第四部分
    if a > 0:
        if b > 0:
            if c > 0:
                result = result * a * b * c
            else:
                result = result * a * b
        else:
            if c > 0:
                result = result * a * c
            else:
                result = result * a
    else:
        result = 0
    
    # 第五部分 - 继续增加行数
    result += 1
    result += 2
    result += 3
    result += 4
    result += 5
    result += 6
    result += 7
    result += 8
    result += 9
    result += 10
    
    # 第六部分
    for i in range(5):
        result += i
    
    # 第七部分
    if result > 100:
        result = 100
    elif result > 50:
        result = 50
    elif result > 25:
        result = 25
    else:
        result = 0
    
    # 第八部分
    result = str(result)
    result = int(result)
    result = float(result)
    
    # 第九部分
    for i in range(3):
        for j in range(3):
            for k in range(3):
                if i == j and j == k:
                    result += i + j + k
    
    # 第十部分
    return result


class VeryLargeClassWithManyMethods:
    """这是一个过大的类，包含太多方法"""
    
    def method1(self):
        pass
    
    def method2(self):
        pass
    
    def method3(self):
        pass
    
    def method4(self):
        pass
    
    def method5(self):
        pass
    
    def method6(self):
        pass
    
    def method7(self):
        pass
    
    def method8(self):
        pass
    
    def method9(self):
        pass
    
    def method10(self):
        pass
    
    def method11(self):
        pass
    
    def method12(self):
        pass
    
    def method13(self):
        pass
    
    def method14(self):
        pass
    
    def method15(self):
        pass
    
    def method16(self):
        pass
    
    def method17(self):
        pass
    
    def method18(self):
        pass
    
    def method19(self):
        pass
    
    def method20(self):
        pass
    
    def method21(self):
        pass
    
    def method22(self):
        pass


def function_with_many_params(a, b, c, d, e, f):
    """这个函数有太多参数"""
    return a + b + c + d + e + f


def simple_function():
    """这是一个简单的函数，不应该触发任何警告"""
    return "Hello, World!"


class GoodClass:
    """这是一个设计良好的类"""
    
    def __init__(self, name):
        self.name = name
    
    def get_name(self):
        return self.name
    
    def set_name(self, name):
        self.name = name
