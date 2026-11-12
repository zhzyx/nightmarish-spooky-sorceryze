# 项目 C++ 编码规范

- 版本：1.1
- 状态：项目级规范
- 适用策略：新增和重写代码执行，存量代码逐步替换

本规范统一本引擎第一方 C++ 代码的可读性、可维护性、跨平台兼容性和生命周期约定。**必须**表示无例外不得合入，**应该**表示默认遵守，**可以**表示按场景选择；例外须在评审中说明。

## 1. 适用范围与存量过渡

适用于 `core/`、`drivers/`、`editor/`、`main/`、`modules/`、`platform/`、`scene/`、`servers/`、`tests/` 等目录中的第一方新增及重写代码。

- 第三方及上游同步代码保持上游风格，避免影响合并。
- 生成代码修改生成器或模板，不直接修改生成结果。
- 外部框架、脚本绑定或对象系统固定要求的名称保持兼容。

| 变更情形 | 执行方式 |
| --- | --- |
| 新增文件或模块 | 完整执行本规范 |
| 存量文件中新增类或函数 | 新增单元执行本规范，既有文件名可以保留 |
| 存量代码小范围修复 | 只改必要区域，不扩大重命名或格式化范围 |
| 整体重写类、函数或文件 | 重写后的完整单元执行本规范 |
| 即将删除的老代码 | 不单独做风格迁移 |

存量代码不批量重命名、重排文件或格式化。过渡期允许同一存量文件暂时存在两种风格，但新增或重写的类、函数内部必须一致。文件重命名、目录调整和全局格式配置切换均单独评审、单独验证。

## 2. 语言基线

- 使用构建系统支持的 **C++17**，不使用更新标准特性；不得使用 `throw`、`try`、`catch`，错误通过 `Error`、返回状态和引擎错误宏处理。
- 鼓励按需使用 `nullptr`、`constexpr`、`static_assert`、`override`／`final`、`= default`／`= delete`、默认成员初始化、范围 `for`、`if constexpr`、`std::move`。
- 原则上显式写出类型。`auto` 仅用于无法写出类型的 lambda、无法合理表达类型的模板代码或显式类型明显损害可读性的迭代器；不得用它隐藏整数宽度、容器、所有权或指针属性。
- 优先命名函数；短小立即调用谓词可以使用 lambda。Lambda 必须显式捕获，不使用 `[=]`、`[&]`；延迟、跨线程或保存回调必须论证捕获对象生命周期。
- 不使用复杂模板、宏或运算符重载掩盖普通逻辑。

## 3. 命名规范

### 3.1 标识符总表

| 对象 | 规则 | 示例或说明 |
| --- | --- | --- |
| C++ 文件 | PascalCase，减少下划线 | `TextureCache.h`、`RenderDevice.cpp` |
| 类、结构体、枚举、别名、命名空间 | PascalCase | `TextureCache`、`RenderSettings`、`Rendering` |
| 函数 | 无下划线的 PascalCase | `LoadTexture()`、`IsVisible()` |
| 宏、编译期常量 | UPPER_SNAKE_CASE | `MAX_TEXTURE_COUNT` |
| 宏参数 | `m_` 前缀 | `m_value` |
| 模板参数 | 清晰的大写开头名称 | `ElementType`；简单模板可用 `T`、`U` |
| 枚举值 | 清晰、统一 | 标志位和序列化枚举显式指定值及底层类型 |

文件以主要内容命名，不重复叠加模块长前缀；重命名时同步更新包含路径、构建文件和引用。函数通常以动词开头，取值函数描述返回值，布尔函数使用 `IsVisible()`、`HasFocus()`、`CanDelete()`、`ShouldUpdate()` 等真假问句；避免 `HandleData()` 等模糊名称。框架固定的既有回调名保持兼容。

### 3.2 变量

局部变量、成员变量和参数采用“**小写类型前缀 + 首字母大写的语义单词**”，语义单词之间不使用下划线。

| 类型 | 前缀 | 示例 | 类型 | 前缀 | 示例 |
| --- | --- | --- | --- | --- | --- |
| 布尔 | `b` | `bEnabled` | 指针 | `p` | `pParent` |
| 枚举 | `e` | `eProcessMode` | 整数、数量、索引 | `n` | `nCount`、`nIndex` |
| 单精度浮点 | `f` | `fDeltaTime` | 双精度浮点 | `d` | `dTimestamp` |
| `String` | `str` | `strPath` | `StringName` | `sn` | `snMethodName` |
| `Ref<T>` | `ref` | `refTexture` | 数组或列表 | `arr` | `arrChildren` |
| 映射容器 | `map` | `mapTextures` | 集合容器 | `set` | `setResources` |
| 数学向量 | `v` | `vPosition` | 结构体值 | `st` | `stConfig` |

其他类型使用稳定、清晰的小写缩写，同一模块不得为同一类型创造多个前缀。名称必须同时表达类型和语义，不使用单独的 `p`、`n`、`b` 代替 `pParent`、`nChildCount`、`bReady`。

### 3.3 参数方向

- 参数遵守变量命名规则。普通输入可写 `strPath`、`pNode`、`bEnabled`；方向不直观时可写 `in_strPath`、`in_pNode`、`in_bEnabled`。
- 输出参数推荐 `out_nResult`、`out_bSuccess`、`out_refTexture`，不使用 `r_`。
- `in_`／`out_` 后仍须带类型前缀，不机械地给所有输入添加 `in_`。

## 4. 大括号与格式

- 函数、类、命名空间和控制语句的块级左大括号必须另起一行。
- `if`、`else`、`else if`、`for`、`while`、`do`、`switch` 等控制块即使只有一行也必须保留大括号；不得把执行逻辑写在控制语句所在行。
- 短函数、访问器和 lambda 同样遵守。`switch` 分支必须明确以 `break`、`return` 或 `[[fallthrough]]` 结束。
- 禁止 `if (bEnabled) Update();`、`if (bEnabled) { Update(); }` 以及省略大括号的换行单行逻辑。
- 使用制表符缩进，显示宽度为 4；指针和引用符号靠近变量名，如 `Node *pNode`、`const String &strPath`。
- `const` 放在类型左侧；变量靠近首次使用位置声明，不遮蔽其他变量；复杂表达式拆成有语义的中间变量。
- 方法之间保留一个空行，避免无意义空行和对齐性大面积差异；文件末尾保留换行。

## 5. 综合示例

```cpp
class TextureCache
{
public:
	Error LoadTexture(
		const String &in_strPath,
		Ref<Texture2D> &out_refTexture);

	bool HasTexture(const String &strPath) const;
	void SetEnabled(bool in_bEnabled);
	void Clear();

private:
	HashMap<String, Ref<Texture2D>> mapTextures;
	bool bEnabled = true;
};

void TextureCache::SetEnabled(bool in_bEnabled)
{
	if (bEnabled == in_bEnabled)
	{
		return;
	}

	bEnabled = in_bEnabled;

	if (!bEnabled)
	{
		Clear();
	}
}

void TextureCache::Clear()
{
	mapTextures.clear();
}
```

## 6. 工程规则

| 领域 | 规则 |
| --- | --- |
| 头文件与依赖 | 保留统一版权头和 `#pragma once`；直接包含所需声明，不依赖传递包含；能前置声明则不包含完整定义；路径与文件位置一致；头文件和全局作用域禁止 `using namespace`，`.cpp` 内部优先匿名命名空间 |
| 类与实现 | `GDCLASS` 按对象系统放置；不影响绑定时按 `public`、`protected`、`private` 组织；数据默认私有，简单数据结构可公开；重写必须 `override`，非继承辅助类可用 `final`，多态基类析构正确；实现默认放 `.cpp`，头文件仅保留模板或必要短实现，强制内联须有性能依据，大函数按职责拆分 |
| 类型与容器 | 序列化、网络、文件格式和 ABI 使用明确宽度整数，内存和地址使用合适尺寸类型；可配置精度用 `real_t`，固定精度用 `float`／`double`，避免窄化及符号混用；使用 `String`、`StringName`、`Vector`、`HashMap`、`HashSet`、`Ref`，不以标准容器替代，第三方标准类型限制在适配边界；用户文本接入翻译机制 |
| API | 只读方法标记 `const`，大型只读输入用 `const &`，输出参数用 `out_`，指针明确空值语义，不以值返回顶层 `const`；避免多个布尔模式参数及易误转换的 `bool`／`String` 重载；参数过多或成组可选配置使用结构体；时间、角度、距离明确单位 |
| 内存与错误 | 使用 `memnew`、`memdelete`，`RefCounted` 优先 `Ref<T>`，场景树对象遵循其所有权；裸指针不表达所有权，异步任务不保存无生命周期保障的指针或引用，`ObjectID` 延迟访问须重新验证，资源、RID、线程和平台句柄明确释放责任；可恢复错误返回 `Error` 或状态值，参数、索引、空指针使用对应 `ERR_FAIL_*`，优先 `_MSG`；仅严重不变量破坏使用终止机制，正常流程不得以错误打印或崩溃作控制流，公共边界验证输入 |
| 并发与平台 | 公共接口说明线程亲和性，使用引擎并发设施并明确锁的保护对象、顺序和范围；持锁时不调用可重入或长阻塞外部代码，不在非允许线程操作场景树或渲染资源，异步回调论证生命周期；平台实现放入平台目录或抽象层，跨平台代码依赖能力接口并集中条件编译，公共头文件不暴露无必要的平台类型，验证受影响平台 |
| 注释与外部代码 | 注释解释意图、约束和原因，标识符及代码注释原则上使用清晰美式英语和准确、包容术语；公共 API 按需说明单位、范围、错误、所有权、空值和线程要求，行为变化同步更新；第三方修改最小化并记录来源和补丁，生成文件只改生成源后重新生成 |

## 7. 评审与工具过渡

| 类别 | 必查项 |
| --- | --- |
| 范围 | 无无关存量改名或格式化；新增和重写单元完整执行；局部修复未扩大范围 |
| 命名与格式 | 文件、函数、变量前缀、参数方向合规；大括号换行；控制块无省略、无同行逻辑 |
| 正确性 | 类型、const、空值、所有权、单位、线程和错误传播清晰；注释与行为一致 |
| 验证 | 完成受影响构建、测试和静态检查；纯文档不机械触发引擎构建；不绕过门禁或真实告警 |

本规范不代表全局 `.clang-format` 或 `.clang-tidy` 已切换，工具适配须单独评审且不得批量迁移存量代码。适配前，新增和重写代码以本规范及人工评审为准；自动格式化不得无差别改写存量文件。现有必需检查仍有效，冲突时先做最小范围工具适配，不绕过检查、以旧工具结果否定本规范或忽略真实告警。
