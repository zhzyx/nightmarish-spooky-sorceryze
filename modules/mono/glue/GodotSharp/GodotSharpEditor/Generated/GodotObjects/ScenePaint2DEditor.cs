namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>This class is available only in the editor and cannot be instantiated. Access it using <see cref="Godot.EditorInterface.GetScenePaint2D()"/>.</para>
/// <para>It provides methods for editor plugins to interact with the scene painting tool.</para>
/// <para>Plugins can register custom scene providers, and set the scene to be painted.</para>
/// </summary>
public partial class ScenePaint2DEditor : Control
{
    private static readonly System.Type CachedType = typeof(ScenePaint2DEditor);

    private static readonly StringName NativeName = "ScenePaint2DEditor";

    internal ScenePaint2DEditor() : this(false)
    {
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: false);
        }
    }

    internal ScenePaint2DEditor(IntPtr ptr) : this(false)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: false);
        }
    }

    internal ScenePaint2DEditor(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.RegisterSceneProvider, 2575427985ul);

    /// <summary>
    /// <para>Registers a custom scene provider.</para>
    /// <para>When the scene picker tool is active and the user clicks on <paramref name="control"/>, the <paramref name="callback"/> is invoked and must return a <see cref="Godot.Node2D"/>.</para>
    /// <para>The returned scene becomes the new painting sample.</para>
    /// </summary>
    public void RegisterSceneProvider(Control control, Callable callback)
    {
        EditorNativeCalls.godot_icall_2_479(MethodBind0, GodotObject.GetPtr(this), GodotObject.GetPtr(control), callback);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.UnregisterSceneProvider, 1496901182ul);

    /// <summary>
    /// <para>Removes a previously registered scene provider.</para>
    /// </summary>
    public void UnregisterSceneProvider(Control control)
    {
        NativeCalls.godot_icall_1_56(MethodBind1, GodotObject.GetPtr(this), GodotObject.GetPtr(control));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetPaintedScene, 2735608809ul);

    /// <summary>
    /// <para>Sets the scene sample to be painted.</para>
    /// </summary>
    public void SetPaintedScene(Node2D scene)
    {
        NativeCalls.godot_icall_1_56(MethodBind2, GodotObject.GetPtr(this), GodotObject.GetPtr(scene));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetPaintedScene, 3536679914ul);

    /// <summary>
    /// <para>Returns the painted scene, or <see langword="null"/> if none is selected. The returned scene's properties can be edited.</para>
    /// <para><b>Warning:</b> Removing and freeing this node will render the editor useless and may cause a crash.</para>
    /// </summary>
    public Node2D GetPaintedScene()
    {
        Node2D ret = (Node2D)NativeCalls.godot_icall_0_53(MethodBind3, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    /// <summary>
    /// Represents the method that handles the <see cref="Godot.ScenePaint2DEditor.ScenePainted"/> event of a <see cref="Godot.ScenePaint2DEditor"/> class.
    /// </summary>
    public delegate void ScenePaintedEventHandler(Node2D node);

    private static void ScenePaintedTrampoline(object delegateObj, NativeVariantPtrArgs args, out godot_variant ret)
    {
        Callable.ThrowIfArgCountMismatch(args, 1);
        ((ScenePaintedEventHandler)delegateObj)(VariantUtils.ConvertTo<Node2D>(args[0]));
        ret = default;
    }

    /// <summary>
    /// <para>Emitted for each new node created during drawing.</para>
    /// <para><b>Example:</b></para>
    /// <para></para>
    /// </summary>
    public unsafe event ScenePaintedEventHandler ScenePainted
    {
        add => Connect(SignalName.ScenePainted, Callable.CreateWithUnsafeTrampoline(value, &ScenePaintedTrampoline));
        remove => Disconnect(SignalName.ScenePainted, Callable.CreateWithUnsafeTrampoline(value, &ScenePaintedTrampoline));
    }

    protected void EmitSignalScenePainted(Node2D node)
    {
        EmitSignal(SignalName.ScenePainted, node);
    }

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_scene_painted = "ScenePainted";

    /// <summary>
    /// Invokes the method with the given name, using the given arguments.
    /// This method is used by Godot to invoke methods from the engine side.
    /// Do not call or override this method.
    /// </summary>
    /// <param name="method">Name of the method to invoke.</param>
    /// <param name="args">Arguments to use with the invoked method.</param>
    /// <param name="ret">Value returned by the invoked method.</param>
#pragma warning disable CS0618 // Member is obsolete
    protected internal override bool InvokeGodotClassMethod(in godot_string_name method, NativeVariantPtrArgs args, out godot_variant ret)
    {
        return base.InvokeGodotClassMethod(method, args, out ret);
    }
#pragma warning restore CS0618

    /// <summary>
    /// Check if the type contains a method with the given name.
    /// This method is used by Godot to check if a method exists before invoking it.
    /// Do not call or override this method.
    /// </summary>
    /// <param name="method">Name of the method to check for.</param>

    protected internal override bool HasGodotClassMethod(in godot_string_name method)
    {
        return base.HasGodotClassMethod(method);
    }

    /// <summary>
    /// Check if the type contains a signal with the given name.
    /// This method is used by Godot to check if a signal exists before raising it.
    /// Do not call or override this method.
    /// </summary>
    /// <param name="signal">Name of the signal to check for.</param>

    protected internal override bool HasGodotClassSignal(in godot_string_name signal)
    {
        if (signal == SignalName.ScenePainted)
        {
            if (HasGodotClassSignal(SignalProxyName_scene_painted.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        return base.HasGodotClassSignal(signal);
    }

    /// <summary>
    /// Cached StringNames for the properties and fields contained in this class, for fast lookup.
    /// </summary>
    public new class PropertyName : Control.PropertyName
    {
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : Control.MethodName
    {
        /// <summary>
        /// Cached name for the 'register_scene_provider' method.
        /// </summary>
        public static readonly StringName RegisterSceneProvider = "register_scene_provider";
        /// <summary>
        /// Cached name for the 'unregister_scene_provider' method.
        /// </summary>
        public static readonly StringName UnregisterSceneProvider = "unregister_scene_provider";
        /// <summary>
        /// Cached name for the 'set_painted_scene' method.
        /// </summary>
        public static readonly StringName SetPaintedScene = "set_painted_scene";
        /// <summary>
        /// Cached name for the 'get_painted_scene' method.
        /// </summary>
        public static readonly StringName GetPaintedScene = "get_painted_scene";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : Control.SignalName
    {
        /// <summary>
        /// Cached name for the 'scene_painted' signal.
        /// </summary>
        public static readonly StringName ScenePainted = "scene_painted";
    }
}
