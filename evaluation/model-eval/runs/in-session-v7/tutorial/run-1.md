---
title: range() 怎么用：从生成序列到内存行为
article_type: 技术教程
theme: bone
audience: 刚学完循环的 Python 初学者
reading_context: 边敲代码边看
purpose: 给出可执行步骤、可观察结果与失败时的回退
thesis: range 生成等差数列而不真正建列表；理解边界与步长是避免差一错误的关键
composition: walkthrough
visual_concept: 代码与说明成对出现，步骤编号即执行顺序
information_shape: 前提 → 基本用法 → 边界 → 内存行为 → 失败排查
asset_strategy: 无图；终端输出本身就是证据
mobile_risk: 代码块横向滚动而不是折行，长行不折
design_rationale: 步骤与规格说明需要细线与留白，选 bone
source: https://docs.python.org/zh-cn/3/tutorial/controlflow.html#the-range-function
---

> 这篇解决一件事：range 的起点、终点、步长各管什么，以及为什么它不会一次性生成列表。

## 前提

Python 3（本文示例在 3.x 上运行）。不需要第三方库。若你在 Python 2 上，`range()` 返回列表，行为不同。

## 第一步：跑一个最小例子

```python
for i in range(5):
    print(i)
```

**完成标准**：屏幕上依次出现 0 到 4，共五行。看不到 5 就是对的——终止值不包含在内。

## 第二步：改起点与步长

```python
list(range(5, 10))
list(range(0, 10, 3))
list(range(-10, -100, -30))
```

三个参数依次是起点、终点（不含）、步长。步长可以是负数，此时起点要大于终点，否则结果为空。

**完成标准**：第二个表达式得到 `[0, 3, 6, 9]`。

## 第三步：按索引迭代

需要下标时，可以组合 `range()` 与 `len()`；多数情况下 `enumerate()` 更方便。

```python
for i, name in enumerate(["甲", "乙"]):
    print(i, name)
```

## 失败时怎么办

- 结果为空列表：先看成起点与终点方向是否与步长一致。
- 少了一个元素：终点不包含，这是设计而非 bug；需要包含时写成终点加步长。
- 直接打印得到 `range(0, 10)`：这是对象表示，不是列表；要列表就 `list(...)`。

::: unknown 版本差异
本文只覆盖 Python 3 教程里的说明；不同 3.x 小版本的具体输出表示可能略有差别，遇到时以 `help(range)` 为准。
:::

::: note 来源与口径
Python 3 教程“更多控制流工具”；PSF License Version 2；示例原样保留。
https://docs.python.org/zh-cn/3/tutorial/controlflow.html#the-range-function
:::
