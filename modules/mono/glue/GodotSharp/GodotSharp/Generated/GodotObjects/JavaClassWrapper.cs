namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>The JavaClassWrapper singleton provides a way for the Godot application to send and receive data through the <a href="https://developer.android.com/training/articles/perf-jni">Java Native Interface</a> (JNI).</para>
/// <para><b>Note:</b> This singleton is only available in Android builds.</para>
/// <para><code>
/// var LocalDateTime = JavaClassWrapper.wrap("java.time.LocalDateTime")
/// var DateTimeFormatter = JavaClassWrapper.wrap("java.time.format.DateTimeFormatter")
/// 
/// var datetime = LocalDateTime.now()
/// var formatter = DateTimeFormatter.ofPattern("dd-MM-yyyy HH:mm:ss")
/// 
/// print(datetime.format(formatter))
/// </code></para>
/// <para><b>Warning:</b> When calling Java methods, be sure to check <see cref="Godot.JavaClassWrapper.GetException()"/> to check if the method threw an exception.</para>
/// </summary>
public static partial class JavaClassWrapper
{
    private static readonly StringName NativeName = "JavaClassWrapper";

    private static JavaClassWrapperInstance singleton;

    public static JavaClassWrapperInstance Singleton =>
        singleton ??= (JavaClassWrapperInstance)InteropUtils.EngineGetSingleton("JavaClassWrapper");

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.Wrap, 1124367868ul);

    /// <summary>
    /// <para>Wraps a class defined in Java, and returns it as a <see cref="Godot.JavaClass"/> <see cref="Godot.GodotObject"/> type that Godot can interact with.</para>
    /// <para>When wrapping inner (nested) classes, use <c>$</c> instead of <c>.</c> to separate them. For example, <c>JavaClassWrapper.wrap("android.view.WindowManager$LayoutParams")</c> wraps the <b>WindowManager.LayoutParams</b> class.</para>
    /// <para><b>Note:</b> To invoke a constructor, call a method with the same name as the class. For example:</para>
    /// <para><code>
    /// var Intent = JavaClassWrapper.wrap("android.content.Intent")
    /// var intent = Intent.Intent()
    /// </code></para>
    /// <para><b>Note:</b> This method only works on Android. On every other platform, this method does nothing and returns an empty <see cref="Godot.JavaClass"/>.</para>
    /// </summary>
    public static JavaClass Wrap(string name)
    {
        JavaClass ret = (JavaClass)NativeCalls.godot_icall_1_551(MethodBind0, GodotObject.GetPtr(Singleton), name);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.GetException, 3277089691ul);

    /// <summary>
    /// <para>Returns the Java exception from the last call into a Java class. If there was no exception, it will return <see langword="null"/>.</para>
    /// <para><b>Note:</b> This method only works on Android. On every other platform, this method will always return <see langword="null"/>.</para>
    /// </summary>
    public static JavaObject GetException()
    {
        JavaObject ret = (JavaObject)NativeCalls.godot_icall_0_87(MethodBind1, GodotObject.GetPtr(Singleton));
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.CreateSamCallback, 2479014754ul);

    /// <summary>
    /// <para>Creates a <see cref="Godot.JavaObject"/> implementing the Java Single Abstract Method (SAM) interface using the Godot <see cref="Godot.Callable"/> as the implementation.</para>
    /// <para>The <paramref name="samInterface"/> <b>must be</b> a Java SAM interface, meaning it must only have a single abstract method to implement.</para>
    /// <para>The <paramref name="callable"/> must be able to handle the same parameter types as the SAM interface method, and must provide the same return type. The <paramref name="callable"/> will be invoked as a callback, passing the arguments from the Java SAM interface method.</para>
    /// <para><code>
    /// var cb = func (content: String) -&gt; void:
    /// 	print(content)
    /// var callback = JavaClassWrapper.create_sam_callback("android.util.Printer", cb)
    /// callback.println("Hello Godot World!")
    /// </code></para>
    /// <para><b>Note:</b> This method only works on Android. On every other platform, this method will always return <see langword="null"/>.</para>
    /// </summary>
    public static JavaObject CreateSamCallback(string samInterface, Callable callable)
    {
        JavaObject ret = (JavaObject)NativeCalls.godot_icall_2_817(MethodBind2, GodotObject.GetPtr(Singleton), samInterface, callable);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.CreateProxy, 2694931752ul);

    /// <summary>
    /// <para>Creates a <see cref="Godot.JavaObject"/> implementing the given Java interfaces using the given <see cref="Godot.GodotObject"/> as the implementation.</para>
    /// <para>The <paramref name="object"/> must contain methods signatures matching the methods signatures from the passed Java <paramref name="interfaces"/>. Invoking methods from the Java <paramref name="interfaces"/> will route to the matching <paramref name="object"/> method.</para>
    /// <para><code>
    /// class PrintProxy:
    /// 	func println(content: String) -&gt; void:
    /// 		print(content)
    /// 
    /// var print_proxy = PrintProxy.new()
    /// var printer_object = JavaClassWrapper.create_proxy(print_proxy, ["android.util.Printer"])
    /// printer_object.println("Hello Godot World!")
    /// </code></para>
    /// <para><b>Note:</b> This method only works on Android. On every other platform, this method will always return <see langword="null"/>.</para>
    /// </summary>
    public static JavaObject CreateProxy(GodotObject @object, string[] interfaces)
    {
        JavaObject ret = (JavaObject)NativeCalls.godot_icall_2_818(MethodBind3, GodotObject.GetPtr(Singleton), GodotObject.GetPtr(@object), interfaces);
        return ret;
    }

    /// <summary>
    /// <para>Creates a <see cref="Godot.JavaObject"/> implementing the given Java interfaces using the given <see cref="Godot.GodotObject"/> as the implementation.</para>
    /// <para>The <paramref name="object"/> must contain methods signatures matching the methods signatures from the passed Java <paramref name="interfaces"/>. Invoking methods from the Java <paramref name="interfaces"/> will route to the matching <paramref name="object"/> method.</para>
    /// <para><code>
    /// class PrintProxy:
    /// 	func println(content: String) -&gt; void:
    /// 		print(content)
    /// 
    /// var print_proxy = PrintProxy.new()
    /// var printer_object = JavaClassWrapper.create_proxy(print_proxy, ["android.util.Printer"])
    /// printer_object.println("Hello Godot World!")
    /// </code></para>
    /// <para><b>Note:</b> This method only works on Android. On every other platform, this method will always return <see langword="null"/>.</para>
    /// </summary>
    public static JavaObject CreateProxy(GodotObject @object, ReadOnlySpan<string> interfaces)
    {
        JavaObject ret = (JavaObject)NativeCalls.godot_icall_2_818(MethodBind3, GodotObject.GetPtr(Singleton), GodotObject.GetPtr(@object), interfaces);
        return ret;
    }

    /// <summary>
    /// Cached StringNames for the properties and fields contained in this class, for fast lookup.
    /// </summary>
    public class PropertyName
    {
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public class MethodName
    {
        /// <summary>
        /// Cached name for the 'wrap' method.
        /// </summary>
        public static readonly StringName Wrap = "wrap";
        /// <summary>
        /// Cached name for the 'get_exception' method.
        /// </summary>
        public static readonly StringName GetException = "get_exception";
        /// <summary>
        /// Cached name for the 'create_sam_callback' method.
        /// </summary>
        public static readonly StringName CreateSamCallback = "create_sam_callback";
        /// <summary>
        /// Cached name for the 'create_proxy' method.
        /// </summary>
        public static readonly StringName CreateProxy = "create_proxy";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public class SignalName
    {
    }
}
