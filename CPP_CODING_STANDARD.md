# 项目 C++ 编码规范

- 版本：1.0
- 状态：项目级规范
- 适用策略：新增和重写代码执行，存量代码逐步替换

本规范用于统一本引擎第一方 C++ 代码的可读性、可维护性、跨平台兼容性和对象生命周期约定。规范以正确性、清晰性和长期维护为优先，不追求语法技巧或为了统一样式制造大规模变更。

## 1. 规则用语

- **必须**：不符合即不应合入，确需例外时必须在评审中说明原因。
- **应该**：默认遵守，存在更合适的局部约定时可以偏离，但应保持一致。
- **可以**：允许根据实际场景选择，不构成强制要求。

## 2. 适用范围与存量过渡

### 2.1 适用范围

本规范适用于本仓库自行维护的 C++ 代码，包括 `core/`、`drivers/`、`editor/`、`main/`、`modules/`、`platform/`、`scene/`、`servers/` 和 `tests/` 等目录中的新增及重写代码。

以下代码遵循各自规则：

- `thirdparty/` 及其他第三方代码保持上游风格，不做本规范迁移。
- 自动生成代码修改生成器或模板，不直接调整生成结果。
- 外部框架、脚本绑定或对象系统固定要求的名称保持兼容。
- 上游同步代码以保持可合并性为优先，不主动制造无关差异。

### 2.2 存量代码不批量迁移

存量代码按照实际维护和重写节奏逐步替换，不进行全库批量重命名、文件重命名或格式化。

| 变更情形 | 执行方式 |
| --- | --- |
| 新增 C++ 文件或模块 | 必须完整执行本规范 |
| 存量文件中新增类或函数 | 新增单元必须执行本规范，既有文件名可以保留 |
| 存量代码的小范围缺陷修复 | 不扩大重命名或格式化范围，只修改必要区域 |
| 整体重写一个类或函数 | 重写后的完整单元必须执行本规范 |
| 整体重写或替换一个文件 | 重写后的完整文件必须执行本规范 |
| 即将删除的老代码 | 不为即将删除的代码单独做风格迁移 |

过渡期允许同一存量文件暂时存在两种风格，但同一个新增或重写的类、函数内部必须保持一致。不得为了“顺便统一”而扩大差异、污染历史或增加合并冲突。

文件重命名、目录调整、全局格式配置切换属于独立变更，应单独评审和验证。

## 3. 语言基线与现代 C++

### 3.1 C++17

代码必须使用当前构建系统支持的 C++17，不使用更新语言标准中的特性。

鼓励使用能够直接提高正确性或可读性的特性：

- `nullptr`
- `constexpr`
- `static_assert`
- `override`／`final`
- `= default`／`= delete`
- 默认成员初始化
- 范围 `for`
- `if constexpr`
- `std::move`

### 3.2 异常与错误传播

引擎代码不得使用 `throw`、`try` 或 `catch`。错误通过 `Error`、返回状态和引擎错误宏处理。

### 3.3 `auto`

原则上显式写出类型，确保代码在普通文本查看器和评审页面中也可读。

仅在以下情况可以使用 `auto`：

- 无法直接写出类型的 lambda。
- 类型无法合理表达的复杂模板代码。
- 显式类型明显损害可读性的迭代器场景。

不得使用 `auto` 隐藏整数宽度、容器类型、对象所有权或指针属性。

### 3.4 Lambda 与模板

- 优先使用命名函数。
- 短小的立即调用谓词可以使用 lambda。
- Lambda 必须显式捕获，不使用 `[=]` 或 `[&]`。
- 延迟执行、跨线程或保存回调时，必须说明捕获对象的生命周期。
- 不使用复杂模板、宏或运算符重载掩盖普通业务逻辑。

## 4. 命名规范

### 4.1 C++ 文件

C++ 源文件和头文件使用 PascalCase，单词首字母大写并尽量减少下划线：

```text
TextureCache.h
TextureCache.cpp
RenderDevice.h
SceneTree.cpp
```

- 文件名应准确表达主要内容。
- 一个文件包含多个类型时，使用最主要、最稳定的类型命名。
- 不为了体现模块层级而重复添加长前缀。
- 重命名既有文件时，必须同步更新包含路径、构建文件和相关引用，并单独验证。

### 4.2 类型与命名空间

类、结构体、枚举、类型别名和命名空间使用 PascalCase：

```cpp
class TextureCache;
struct RenderSettings;
enum class ProcessMode;
namespace Rendering;
```

模板参数使用清晰的大写开头名称：

```cpp
template <typename ElementType>
class Container;
```

简单、局部的模板也可以使用 `T`、`U` 等惯用参数名。

### 4.3 函数

函数名使用 PascalCase，不使用下划线：

```cpp
LoadTexture();
GetTexture();
SetEnabled();
IsVisible();
UpdateTransform();
ClearUnusedResources();
```

命名要求：

- 普通函数使用动词开头，表达执行的动作。
- 获取值的函数描述返回值，例如 `GetWidth()`。
- 布尔函数表达真假问题，例如 `IsVisible()`、`HasFocus()`、`CanDelete()`、`ShouldUpdate()`。
- 避免含义模糊的 `HandleData()`、`ProcessThing()`，应明确处理对象和结果。
- 引擎或外部框架固定要求的既有回调名保持兼容；新增普通函数必须遵守本规则。

### 4.4 变量

局部变量、成员变量和参数采用“小写类型前缀 + 首字母大写的语义单词”，语义单词之间不使用下划线。

基础前缀如下：

| 类型 | 前缀 | 示例 |
| --- | --- | --- |
| 布尔 | `b` | `bEnabled`、`bVisible`、`bCanMove` |
| 指针 | `p` | `pParent`、`pTexture`、`pRenderDevice` |
| 枚举 | `e` | `eState`、`eProcessMode` |
| 整数、数量、索引 | `n` | `nCount`、`nIndex`、`nWidth` |
| 单精度浮点 | `f` | `fSpeed`、`fDeltaTime` |
| 双精度浮点 | `d` | `dTimestamp`、`dTotalTime` |
| `String` | `str` | `strPath`、`strUserName` |
| `StringName` | `sn` | `snMethodName`、`snSignalName` |
| `Ref<T>` | `ref` | `refTexture`、`refMaterial` |
| 数组或列表容器 | `arr` | `arrTextures`、`arrChildren` |
| 映射容器 | `map` | `mapTextures`、`mapEntries` |
| 集合容器 | `set` | `setNames`、`setResources` |
| 数学向量 | `v` | `vPosition`、`vDirection` |
| 结构体值 | `st` | `stConfig`、`stRenderSettings` |

未列出的类型使用稳定、清晰的小写类型缩写。同一模块不得为同一种类型随意创造多个前缀。

示例：

```cpp
bool bEnabled = true;
int32_t nTextureCount = 0;
float fDeltaTime = 0.0f;
Node *pParent = nullptr;
ProcessMode eProcessMode = ProcessMode::Default;
String strResourcePath;
Ref<Texture2D> refTexture;
```

变量名必须同时表达类型和语义，不能只保留类型前缀：

```cpp
// 不推荐。
Node *p;
int32_t n;
bool b;

// 推荐。
Node *pParent;
int32_t nChildCount;
bool bReady;
```

### 4.5 输入与输出参数

参数同样遵守变量命名规则。需要明确参数方向时，可以使用 `in_` 和 `out_`：

```cpp
Error LoadTexture(
	const String &in_strPath,
	Ref<Texture2D> &out_refTexture);

bool TryGetTextureCount(int32_t &out_nCount) const;
void SetEnabled(bool bEnabled);
```

具体约定：

- 普通输入参数可以写成 `strPath`、`pNode`、`bEnabled`。
- 需要强调输入方向时写成 `in_strPath`、`in_pNode`、`in_bEnabled`。
- 输出参数推荐使用 `out_`，例如 `out_nResult`、`out_bSuccess`、`out_pObject`。
- 不使用 `r_` 作为输出参数前缀。
- `in_`／`out_` 后面的名称仍必须带类型前缀。
- 不要只为形式统一而给所有参数机械添加 `in_`；主要用于输入、输出方向不直观的接口。

### 4.6 常量、宏与枚举值

- 宏使用 UPPER_SNAKE_CASE。
- 宏参数使用 `m_` 前缀。
- 编译期常量可以使用 UPPER_SNAKE_CASE。
- 枚举类型使用 PascalCase，枚举值保持清晰、统一。
- 标志位和序列化枚举应显式指定值及底层类型。

## 5. 大括号与代码格式

### 5.1 大括号另起一行

函数、类、命名空间以及控制语句的块级左大括号必须另起一行：

```cpp
class TextureCache
{
public:
	void Clear();
};

void TextureCache::Clear()
{
	mapTextures.clear();
}
```

### 5.2 所有控制块必须保留大括号

即使语句块只有一行，也不得省略大括号：

```cpp
if (bEnabled)
{
	Update();
}
```

禁止以下写法：

```cpp
if (bEnabled)
	Update();

if (bEnabled) Update();

if (bEnabled) { Update(); }
```

该规则适用于 `if`、`else`、`else if`、`for`、`while`、`do`、`switch` 等流程控制语句：

```cpp
if (pTexture != nullptr)
{
	UseTexture(pTexture);
}
else if (refFallback.is_valid())
{
	UseTexture(refFallback.ptr());
}
else
{
	UseDefaultTexture();
}

for (int32_t nIndex = 0; nIndex < nTextureCount; ++nIndex)
{
	UpdateTexture(nIndex);
}

while (bPending)
{
	ProcessNextTask();
}
```

要求：

- 不在 `if`、`for`、`while` 等语句所在行直接编写执行逻辑。
- `else` 和 `else if` 的执行块同样必须使用大括号。
- `switch` 的每个分支必须明确以 `break`、`return` 或 `[[fallthrough]]` 结束。
- 短函数、访问器和 lambda 也不得为了压缩行数而违反块级大括号规则。

### 5.3 其他格式

- 使用制表符缩进，显示宽度为 4。
- 指针和引用符号靠近变量名：

```cpp
Node *pNode;
const String &strPath;
Ref<Texture2D> &out_refTexture;
```

- `const` 放在类型左侧。
- 变量在接近首次使用的位置声明。
- 禁止变量遮蔽。
- 复杂表达式应拆分为具有明确语义的中间变量。
- 方法之间保留一个空行，避免无意义的连续空行。
- 文件末尾保留换行。
- 不为了对齐而产生大面积无关差异。

## 6. 文件、类与依赖管理

### 6.1 头文件

- 第一方公开源文件保留仓库统一版权头。
- 头文件必须使用 `#pragma once`。
- 直接包含自身使用的声明，不依赖传递包含。
- 可以使用前置声明时，不在头文件中包含完整定义。
- 包含路径必须与实际文件位置一致；重命名文件时同步更新所有引用。

### 6.2 类组织

- `GDCLASS` 等引擎宏按对象系统要求放置。
- 在不影响宏和绑定的情况下，按 `public`、`protected`、`private` 组织接口。
- 数据成员默认私有，简单数据结构可以公开成员。
- 重写虚函数必须写 `override`。
- 不用于继承的辅助类可以使用 `final`。
- 多态基类必须保证析构方式正确。

### 6.3 实现与内联

- 函数实现默认放在 `.cpp`。
- 头文件中仅保留模板实现或有明确必要的短实现。
- 强制内联不得作为默认优化手段，应有性能依据。
- 大型函数按职责拆分，而不是通过注释分区维持超长实现。
- 头文件和全局作用域禁止 `using namespace`；`.cpp` 内部实现优先使用匿名命名空间。

## 7. 基础类型、容器与 API 设计

### 7.1 基础类型与容器

- 序列化、网络协议、文件格式和 ABI 边界必须使用明确宽度的整数类型。
- 内存大小和平台地址尺寸使用合适的尺寸类型。
- 引擎可配置数学精度使用 `real_t`；固定精度场景明确使用 `float` 或 `double`。
- 避免无意识的窄化转换及有符号／无符号混用。
- 使用 `String`、`StringName`、`Vector`、`HashMap`、`HashSet`、`Ref` 等引擎类型。
- 不使用标准容器替代引擎容器；第三方接口需要的标准类型应限制在适配边界。
- 面向用户的文本必须接入引擎翻译机制。

### 7.2 参数与返回值

- 不修改对象的方法必须标记为 `const`。
- 不修改的大型输入对象使用 `const &`。
- 输出参数使用明确的 `out_` 语义。
- 指针参数必须说明是否允许为 `nullptr`。
- 不以值类型返回顶层 `const`。
- 避免使用多个布尔参数切换行为，优先使用枚举、标志或参数结构体。
- 参数过多或存在成组可选配置时，使用专用参数结构体。
- 避免容易产生意外转换的 `bool`／`String` 重载组合。
- 时间、角度、距离等参数应明确单位。

## 8. 内存、生命周期与错误处理

### 8.1 内存与对象

- 使用引擎提供的 `memnew`、`memdelete` 和对应分配器接口。
- `RefCounted` 对象优先使用 `Ref<T>`。
- 场景树对象遵循场景树所有权和释放规则。
- 裸指针默认不表达所有权。
- 异步任务不得保存没有生命周期保障的裸指针或对象引用。
- 使用 `ObjectID` 延迟访问对象时，必须重新解析并验证对象仍然有效。
- 资源、RID、线程和平台句柄必须具有明确的释放责任方。

### 8.2 错误处理

- 可恢复错误返回 `Error` 或合适的状态值。
- 参数、空指针和索引检查使用对应的 `ERR_FAIL_*` 宏。
- 优先使用带 `_MSG` 的版本，提供能够定位问题的信息。
- 索引错误使用索引专用宏，空指针使用空指针专用宏。
- 严重内部不变量破坏才使用终止机制。
- 正常业务流程不得依赖错误打印或崩溃宏进行控制流。
- 公共边界必须验证外部输入。

## 9. 并发与平台代码

### 9.1 并发

- 公共类型和接口必须说明线程亲和性。
- 使用引擎提供的互斥、读写锁、原子计数和线程设施。
- 锁的保护对象、顺序和持有范围必须清晰。
- 不在持锁期间调用可能重入或长时间阻塞的外部代码。
- 不在非允许线程直接操作场景树或渲染资源。
- 异步回调必须论证捕获对象的生命周期。

### 9.2 平台

- 平台实现放入对应平台目录或硬件抽象层。
- 跨平台代码优先依赖能力接口，不散布操作系统判断。
- 条件编译应尽量集中，避免割裂普通业务逻辑。
- 公共头文件不得无必要地暴露平台头文件和平台类型。
- 修改共享代码时，应验证实际受影响平台。

## 10. 注释、第三方与生成代码

- 注释解释意图、约束和原因，不复述代码表面行为。
- 标识符和代码注释原则上使用清晰的美式英语。
- 使用准确、包容的术语；上游协议或兼容字段除外。
- 公共 API 根据需要说明单位、范围、错误、所有权、空值语义和线程要求。
- 修改行为时必须同步更新注释。
- 第三方代码保持上游风格，必要修改应最小化并保留来源及补丁记录。
- 不手工修改生成文件，必须调整生成源并重新生成。

## 11. 综合示例

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

示例体现了类型的 PascalCase、函数的无下划线 PascalCase、变量类型前缀、参数方向、大括号换行以及控制块不可省略等核心约定。

## 12. 评审检查清单

### 范围与迁移

- 变更没有包含无关的存量重命名、文件重命名或格式化。
- 新增文件和整体重写单元完整执行本规范。
- 局部修复没有为了统一样式扩大修改范围。
- 第三方、生成代码和框架固定名称按各自兼容规则处理。

### 命名与格式

- 新增 C++ 文件使用 PascalCase，并尽量减少下划线。
- 函数使用无下划线的 PascalCase。
- 变量具有准确的类型前缀和清晰的语义。
- 参数方向清晰，输出参数不使用 `r_`。
- 块级大括号另起一行，所有流程控制块保留大括号。
- 没有在控制语句所在行直接编写执行逻辑。

### 正确性与接口

- 类型宽度、const、空值、所有权和单位清晰。
- 没有不受保护的对象生命周期或跨线程访问。
- 可恢复错误通过状态返回，不使用异常。
- 公共 API 注释和实际行为一致。

### 验证与工具

- 完成受影响范围的构建、测试和静态检查；纯文档变更不机械触发引擎构建。
- 没有通过绕过既有门禁来消除新旧规范冲突。
- 没有通过批量改写存量代码来适应自动工具。
- 工具配置尚未覆盖的规则由代码评审检查，不能把“工具未报警”等同于符合本规范。

## 13. 自动工具过渡

本规范合入不代表全局 `.clang-format` 或 `.clang-tidy` 已同步切换。工具适配属于独立变更，必须避免对存量代码产生批量格式化或命名迁移。

在工具完成适配前：

- 新增和重写代码以本规范及人工评审为准。
- 使用自动格式化时，不得让其无差别改写整个存量文件。
- 现有必需检查仍然有效；发生规则冲突时，应先完成最小范围的工具策略适配，不绕过检查。
- 不以旧工具能够检查通过作为违反本规范的理由，也不以新规范为由忽略真实告警。
