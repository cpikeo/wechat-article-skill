---
title: 不再数错 range() 的边界
article_type: 技术教程
theme: paper
audience: 写循环时反复调试边界的读者
reading_context: 在工作台前对照执行
purpose: 把边界规则、负步长和懒生成拆成可验证的三步
thesis: 差一错误来自把终止值当成包含；内存疑问来自把 range 当成列表
composition: walkthrough
visual_concept: 每个结论下面立刻跟一个可运行的验证，编号就是执行顺序
information_shape: 前提 → 验证 → 反例 → 自查
asset_strategy: 无图；输出行即证据
mobile_risk: 代码块长行横向滚动，正文不缩字
design_rationale: 需要清晰编号与行列的理性阅读，paper
source: https://docs.python.org/zh-cn/3/tutorial/controlflow.html#the-range-function
---

> 两条规则记住就不会数错：终止值不含；range 不建列表。

## 前提与版本

Python 3。示例不依赖第三方库。Python 2 的 `range()` 返回列表，本文结论不适用。

## 规则一：终止值不包含

```python
for i in range(5):
    print(i)
```

**验证**：输出 0 到 4。`range(10)` 生成 10 个值，正好是长度 10 的序列的全部合法索引。

## 规则二：起点与步长

```python
list(range(5, 10))       # [5, 6, 7, 8, 9]
list(range(0, 10, 3))    # [0, 3, 6, 9]
list(range(-10, -100, -30))
```

步长为负时起点必须大于终点，否则结果是空列表。这一点比记语法更容易出错。

## 反面例子：以为它在建列表

```python
r = range(0, 10)
print(r)        # range(0, 10)
```

它和列表在很多方面行为一致，但并没有真正生成含全部项的列表；只在被迭代时逐个返回所需项，从而节省空间。

## 三步自查

1. 输出为空 → 检查方向与步长。
2. 少了元素 → 终止值不含。
3. 需要下标 → 先试 `enumerate()`，再考虑 `range(len(...))`。

::: unknown 边界外的情况
迭代 range 的同时修改被遍历的容器，后果不在原文范围内；需要时先复制一份。
:::

::: note 来源与口径
Python 3 教程“更多控制流工具”；PSF License Version 2；示例保持原样。
https://docs.python.org/zh-cn/3/tutorial/controlflow.html#the-range-function
:::
