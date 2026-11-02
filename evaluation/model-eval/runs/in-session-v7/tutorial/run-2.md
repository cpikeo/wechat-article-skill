---
title: 三个参数、一个陷阱：range() 的实用手册
article_type: 技术教程
theme: bone
audience: 需要写循环的 Python 使用者
reading_context: 卡住时搜索进来，逐段照做
purpose: 用可观察输出说明起止与步长，并给出常见错误的自查顺序
thesis: range 的边界规则与懒生成是两件要分开理解的事
composition: walkthrough
visual_concept: 短步骤 + 代码 + 输出三件套，靠编号推进
information_shape: 用例 → 参数 → 边界 → 内存 → 自查
asset_strategy: 无图；代码输出是唯一需要的证据
mobile_risk: 代码行较长时横向滚动，不缩字号
design_rationale: 教程需要规格线和小节感，bone 比 froat 更适合
source: https://docs.python.org/zh-cn/3/tutorial/controlflow.html#the-range-function
---

> range 生成等差数列，且不包含终止值；它不真的建列表，只在迭代时逐个给出。

## 最小可运行例子

```python
for i in range(5):
    print(i)
```

输出 0、1、2、3、4。没有 5。

## 参数的顺序

1. `range(stop)`：从 0 开始，不含 stop。
2. `range(start, stop)`：从 start 开始，不含 stop。
3. `range(start, stop, step)`：步长可以为负。

```python
list(range(5, 10))
list(range(0, 10, 3))
list(range(-10, -100, -30))
```

**自查**：把三个表达式的输出写下来再看下一节。第二个应为 `[0, 3, 6, 9]`。

## 它为什么省内存

直接打印会得到 `range(0, 10)`。它和列表在行为上很像，但没有真正生成含全部项的列表；被迭代时才逐个返回所需项。

需要同时拿到下标和元素时，组合 `range()` 与 `len()` 可以，但 `enumerate()` 更直接。

## 出错了按这个顺序查

1. 结果为空：起点、终点与步长方向是否矛盾？
2. 少一个元素：是不是忘了终止值不含？
3. 打印成 `range(...)`：是不是忘了 `list()`？
4. 想在迭代中改序列长度：先复制一份再改。

::: unknown 迭代期修改
原文没有说明在迭代 range 对象时修改外部容器的具体后果；这类情况建议先复制序列再遍历。
:::

::: note 来源与口径
Python 3 教程；PSF License Version 2；代码示例按原样引用。
https://docs.python.org/zh-cn/3/tutorial/controlflow.html#the-range-function
:::
