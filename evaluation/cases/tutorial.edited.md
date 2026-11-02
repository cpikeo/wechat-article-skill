---
title: Python range() 为什么不包含终点
author: Python文档（评估摘录）
theme: paper
audience: 刚开始写Python循环的学习者
reading_context: 边看边在解释器中运行示例
purpose: 解释range的起点、终点和步长，并避免把它误当成列表
thesis: range按“起点包含、终点不含”的规则生成可迭代整数序列
article_type: 技术教程
composition: explainer
visual_concept: 用“规则—运行结果—常见选择”的单线流程降低跳读成本
information_shape: 流程 + 规则 + 示例
asset_strategy: 无图；代码输出比装饰图更能解释规则
mobile_risk: 代码行保持短小，避免横向滚动
source: https://docs.python.org/zh-cn/3/tutorial/controlflow.html#the-range-function
---

> 先记一条：`range` 包含起点，不包含终点。

## 先运行最小例子

```python
for i in range(5):
    print(i)
```

输出从0到4，共5个整数。终点5不在结果中。

## 再读三个参数

`range(start, stop, step)` 分别表示起点、终点和步长。起点可以不是0，步长也可以是负数。

```python
list(range(5, 10))        # 5, 6, 7, 8, 9
list(range(0, 10, 3))     # 0, 3, 6, 9
list(range(-10, -100, -30))  # -10, -40, -70
```

::: peak
判断最后一个值时，不要只看终点数值，而要看按这个步长终点之前最后能到哪里。
:::

## 最后分清range与列表

直接打印 `range(10)`，看到的是 `range(0, 10)`。range是可迭代对象，不会预先生成一个包含全部整数的列表；需要列表时再显式写 `list(range(10))`。

如果只是按索引同时读取序列，官方教程提醒：多数情况下，`enumerate()` 比 `range(len(sequence))` 更直接。

::: note 来源与许可
Python 3教程“更多控制流工具”；PSF License Version 2；示例注释为本评估稿补充。
https://docs.python.org/zh-cn/3/tutorial/controlflow.html#the-range-function
:::
