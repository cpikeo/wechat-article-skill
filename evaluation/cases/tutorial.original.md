---
title: range() 函数
author: Python文档（评估摘录）
theme: paper
source: https://docs.python.org/zh-cn/3/tutorial/controlflow.html#the-range-function
---

内置函数 `range()` 用于生成等差数列：

```python
for i in range(5):
    print(i)
```

生成的序列绝不会包括给定的终止值；`range(10)` 生成10个值——长度为10的序列的所有合法索引。range可以不从0开始，且可以按给定的步长递增，即使是负数步长。

```python
list(range(5, 10))
list(range(0, 10, 3))
list(range(-10, -100, -30))
```

要按索引迭代序列，可以组合使用 `range()` 和 `len()`。不过大多数情况下，`enumerate()` 函数很方便。

如果直接打印一个range，会得到 `range(0, 10)`。range返回的对象在很多方面和列表的行为一样，但并没有真正生成一个含有全部项的列表；它只在被迭代时逐个返回所需的项，从而节省空间。

::: note 来源与许可
Python 3 教程“更多控制流工具”；PSF License Version 2；版本内容会更新。
https://docs.python.org/zh-cn/3/tutorial/controlflow.html#the-range-function
:::
