"""
测试示例文件 - 包含各种代码异味
"""


def long_function_with_many_issues(data):
    """
    这是一个过长的函数，有很多问题
    """
    result = []
    
    # 复杂的嵌套逻辑
    for item in data:
        if item is not None:
            if isinstance(item, dict):
                if 'value' in item:
                    if item['value'] > 0:
                        if item['value'] < 100:
                            for i in range(item['value']):
                                if i % 2 == 0:
                                    result.append(i * 2)
                                else:
                                    result.append(i * 3)
                    else:
                        if item['value'] < 0:
                            result.append(0)
                        else:
                            result.append(1)
                else:
                    result.append(None)
            elif isinstance(item, list):
                for sub_item in item:
                    if sub_item is not None:
                        if isinstance(sub_item, int):
                            if sub_item > 0:
                                result.append(sub_item * 2)
                            else:
                                result.append(sub_item)
                        else:
                            result.append(str(sub_item))
            else:
                result.append(item)
        else:
            result.append(None)
    
    # 重复代码块
    processed_data = []
    for item in result:
        if item is not None:
            if isinstance(item, int):
                if item > 0:
                    processed_data.append(item * 2)
                else:
                    processed_data.append(item)
            else:
                processed_data.append(str(item))
        else:
            processed_data.append(None)
    
    # 又一次重复
    final_data = []
    for item in processed_data:
        if item is not None:
            if isinstance(item, int):
                if item > 0:
                    final_data.append(item * 2)
                else:
                    final_data.append(item)
            else:
                final_data.append(str(item))
        else:
            final_data.append(None)
    
    return final_data


def function_with_too_many_params(param1, param2, param3, param4, param5, param6):
    """参数过多的函数"""
    return param1 + param2 + param3 + param4 + param5 + param6


class LargeClass:
    """过大的类"""
    
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


def no_docstring_function():
    return 42


def simple_function(x):
    """简单的函数，没有问题"""
    return x * 2
