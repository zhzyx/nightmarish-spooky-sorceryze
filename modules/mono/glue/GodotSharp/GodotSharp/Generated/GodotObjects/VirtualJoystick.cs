namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>A customizable on-screen joystick control designed for touchscreen devices. It allows users to provide directional input by dragging a virtual tip within a defined circular area.</para>
/// <para>This control can simulate directional actions (see <see cref="Godot.VirtualJoystick.ActionUp"/>, <see cref="Godot.VirtualJoystick.ActionDown"/>, <see cref="Godot.VirtualJoystick.ActionLeft"/>, and <see cref="Godot.VirtualJoystick.ActionRight"/>), which are triggered when the joystick is moved in the corresponding directions.</para>
/// </summary>
public partial class VirtualJoystick : Control
{
    public enum JoystickModeEnum : long
    {
        /// <summary>
        /// <para>The joystick doesn't move.</para>
        /// </summary>
        Fixed = 0,
        /// <summary>
        /// <para>The joystick is moved to the initial touch position as long as it's within the joystick's bounds. It moves back to its original position when released.</para>
        /// </summary>
        Dynamic = 1,
        /// <summary>
        /// <para>The joystick is moved to the initial touch position as long as it's within the joystick's bounds. It will follow the touch input if it goes outside the joystick's range. It moves back to its original position when released.</para>
        /// </summary>
        Following = 2
    }

    public enum VisibilityModeEnum : long
    {
        /// <summary>
        /// <para>The joystick is always visible.</para>
        /// </summary>
        Always = 0,
        /// <summary>
        /// <para>The joystick is only visible when being touched.</para>
        /// </summary>
        WhenTouched = 1
    }

    /// <summary>
    /// <para>The joystick mode to use.</para>
    /// </summary>
    public VirtualJoystick.JoystickModeEnum JoystickMode
    {
        get
        {
            return GetJoystickMode();
        }
        set
        {
            SetJoystickMode(value);
        }
    }

    /// <summary>
    /// <para>The size of the joystick in pixels.</para>
    /// </summary>
    public float JoystickSize
    {
        get
        {
            return GetJoystickSize();
        }
        set
        {
            SetJoystickSize(value);
        }
    }

    /// <summary>
    /// <para>The size of the joystick tip in pixels.</para>
    /// </summary>
    public float TipSize
    {
        get
        {
            return GetTipSize();
        }
        set
        {
            SetTipSize(value);
        }
    }

    /// <summary>
    /// <para>The ratio of the joystick size that defines the joystick deadzone. The joystick tip must move beyond this ratio before being considered active.</para>
    /// <para>This deadzone is applied before triggering input actions and affects the joystick's input vector and all related signals.</para>
    /// <para>Note that input actions may also define their own deadzones in the InputMap. If both are set, the joystick deadzone is applied first, followed by the action's deadzone.</para>
    /// <para>By default, this value is <c>0.0</c>, meaning the joystick does not apply its own deadzone and relies entirely on the InputMap action deadzones.</para>
    /// </summary>
    public float DeadzoneRatio
    {
        get
        {
            return GetDeadzoneRatio();
        }
        set
        {
            SetDeadzoneRatio(value);
        }
    }

    /// <summary>
    /// <para>The multiplier applied to the joystick's radius that defines the clamp zone.</para>
    /// <para>This zone limits how far the joystick tip can move from its center before being clamped.</para>
    /// <para>A value of <c>1.0</c> means the tip can move up to the edge of the joystick's visual size.</para>
    /// <para>In <see cref="Godot.VirtualJoystick.JoystickModeEnum.Following"/> mode, this radius also determines how far the finger can move before the joystick base starts following the touch input.</para>
    /// </summary>
    public float ClampzoneRatio
    {
        get
        {
            return GetClampzoneRatio();
        }
        set
        {
            SetClampzoneRatio(value);
        }
    }

    /// <summary>
    /// <para>The initial position of the joystick as a ratio of the control's size. <c>(0, 0)</c> is top-left and <c>(1, 1)</c> is bottom-right.</para>
    /// </summary>
    public Vector2 InitialOffsetRatio
    {
        get
        {
            return GetInitialOffsetRatio();
        }
        set
        {
            SetInitialOffsetRatio(value);
        }
    }

    /// <summary>
    /// <para>The action to trigger when the joystick is moved left.</para>
    /// </summary>
    public StringName ActionLeft
    {
        get
        {
            return GetActionLeft();
        }
        set
        {
            SetActionLeft(value);
        }
    }

    /// <summary>
    /// <para>The action to trigger when the joystick is moved right.</para>
    /// </summary>
    public StringName ActionRight
    {
        get
        {
            return GetActionRight();
        }
        set
        {
            SetActionRight(value);
        }
    }

    /// <summary>
    /// <para>The action to trigger when the joystick is moved up.</para>
    /// </summary>
    public StringName ActionUp
    {
        get
        {
            return GetActionUp();
        }
        set
        {
            SetActionUp(value);
        }
    }

    /// <summary>
    /// <para>The action to trigger when the joystick is moved down.</para>
    /// </summary>
    public StringName ActionDown
    {
        get
        {
            return GetActionDown();
        }
        set
        {
            SetActionDown(value);
        }
    }

    /// <summary>
    /// <para>The visibility mode to use.</para>
    /// </summary>
    public VirtualJoystick.VisibilityModeEnum VisibilityMode
    {
        get
        {
            return GetVisibilityMode();
        }
        set
        {
            SetVisibilityMode(value);
        }
    }

    private static readonly System.Type CachedType = typeof(VirtualJoystick);

    private static readonly StringName NativeName = "VirtualJoystick";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public VirtualJoystick() : this(false)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: false);
        }
    }

    internal VirtualJoystick(IntPtr ptr) : this(false)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: false);
        }
    }

    internal VirtualJoystick(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetJoystickMode, 1316760817ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetJoystickMode(VirtualJoystick.JoystickModeEnum mode)
    {
        NativeCalls.godot_icall_1_38(MethodBind0, GodotObject.GetPtr(this), (int)mode);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetJoystickMode, 2694680530ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public VirtualJoystick.JoystickModeEnum GetJoystickMode()
    {
        VirtualJoystick.JoystickModeEnum ret = (VirtualJoystick.JoystickModeEnum)NativeCalls.godot_icall_0_39(MethodBind1, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetJoystickSize, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetJoystickSize(float size)
    {
        NativeCalls.godot_icall_1_91(MethodBind2, GodotObject.GetPtr(this), size);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetJoystickSize, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetJoystickSize()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind3, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetTipSize, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetTipSize(float size)
    {
        NativeCalls.godot_icall_1_91(MethodBind4, GodotObject.GetPtr(this), size);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetTipSize, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetTipSize()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind5, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetDeadzoneRatio, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetDeadzoneRatio(float ratio)
    {
        NativeCalls.godot_icall_1_91(MethodBind6, GodotObject.GetPtr(this), ratio);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetDeadzoneRatio, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetDeadzoneRatio()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind7, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind8 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetClampzoneRatio, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetClampzoneRatio(float ratio)
    {
        NativeCalls.godot_icall_1_91(MethodBind8, GodotObject.GetPtr(this), ratio);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind9 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetClampzoneRatio, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetClampzoneRatio()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind9, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind10 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetInitialOffsetRatio, 743155724ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public unsafe void SetInitialOffsetRatio(Vector2 ratio)
    {
        NativeCalls.godot_icall_1_36(MethodBind10, GodotObject.GetPtr(this), &ratio);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind11 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetInitialOffsetRatio, 3341600327ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Vector2 GetInitialOffsetRatio()
    {
        Vector2 ret = NativeCalls.godot_icall_0_37(MethodBind11, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind12 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetActionLeft, 3304788590ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetActionLeft(StringName action)
    {
        NativeCalls.godot_icall_1_88(MethodBind12, GodotObject.GetPtr(this), (godot_string_name)(action?.NativeValue ?? default));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind13 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetActionLeft, 2002593661ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public StringName GetActionLeft()
    {
        StringName ret = NativeCalls.godot_icall_0_89(MethodBind13, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind14 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetActionRight, 3304788590ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetActionRight(StringName action)
    {
        NativeCalls.godot_icall_1_88(MethodBind14, GodotObject.GetPtr(this), (godot_string_name)(action?.NativeValue ?? default));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind15 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetActionRight, 2002593661ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public StringName GetActionRight()
    {
        StringName ret = NativeCalls.godot_icall_0_89(MethodBind15, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind16 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetActionUp, 3304788590ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetActionUp(StringName action)
    {
        NativeCalls.godot_icall_1_88(MethodBind16, GodotObject.GetPtr(this), (godot_string_name)(action?.NativeValue ?? default));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind17 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetActionUp, 2002593661ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public StringName GetActionUp()
    {
        StringName ret = NativeCalls.godot_icall_0_89(MethodBind17, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind18 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetActionDown, 3304788590ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetActionDown(StringName action)
    {
        NativeCalls.godot_icall_1_88(MethodBind18, GodotObject.GetPtr(this), (godot_string_name)(action?.NativeValue ?? default));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind19 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetActionDown, 2002593661ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public StringName GetActionDown()
    {
        StringName ret = NativeCalls.godot_icall_0_89(MethodBind19, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind20 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetVisibilityMode, 2638298545ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetVisibilityMode(VirtualJoystick.VisibilityModeEnum mode)
    {
        NativeCalls.godot_icall_1_38(MethodBind20, GodotObject.GetPtr(this), (int)mode);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind21 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetVisibilityMode, 3530872950ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public VirtualJoystick.VisibilityModeEnum GetVisibilityMode()
    {
        VirtualJoystick.VisibilityModeEnum ret = (VirtualJoystick.VisibilityModeEnum)NativeCalls.godot_icall_0_39(MethodBind21, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    /// <summary>
    /// <para>Emitted when the joystick is pressed.</para>
    /// </summary>
    public event Action Pressed
    {
        add => Connect(SignalName.Pressed, Callable.From(value));
        remove => Disconnect(SignalName.Pressed, Callable.From(value));
    }

    protected void EmitSignalPressed()
    {
        EmitSignal(SignalName.Pressed);
    }

    /// <summary>
    /// <para>Emitted when the joystick is released without moving the tip.</para>
    /// </summary>
    public event Action Tapped
    {
        add => Connect(SignalName.Tapped, Callable.From(value));
        remove => Disconnect(SignalName.Tapped, Callable.From(value));
    }

    protected void EmitSignalTapped()
    {
        EmitSignal(SignalName.Tapped);
    }

    /// <summary>
    /// Represents the method that handles the <see cref="Godot.VirtualJoystick.Released"/> event of a <see cref="Godot.VirtualJoystick"/> class.
    /// </summary>
    public delegate void ReleasedEventHandler(Vector2 inputVector);

    private static void ReleasedTrampoline(object delegateObj, NativeVariantPtrArgs args, out godot_variant ret)
    {
        Callable.ThrowIfArgCountMismatch(args, 1);
        ((ReleasedEventHandler)delegateObj)(VariantUtils.ConvertTo<Vector2>(args[0]));
        ret = default;
    }

    /// <summary>
    /// <para>Emitted when the joystick is released. The <c>inputVector</c> is the final input direction and strength, with a length between <c>0.0</c> and <c>1.0</c>.</para>
    /// </summary>
    public unsafe event ReleasedEventHandler Released
    {
        add => Connect(SignalName.Released, Callable.CreateWithUnsafeTrampoline(value, &ReleasedTrampoline));
        remove => Disconnect(SignalName.Released, Callable.CreateWithUnsafeTrampoline(value, &ReleasedTrampoline));
    }

    protected void EmitSignalReleased(Vector2 inputVector)
    {
        EmitSignal(SignalName.Released, inputVector);
    }

    /// <summary>
    /// Represents the method that handles the <see cref="Godot.VirtualJoystick.Flicked"/> event of a <see cref="Godot.VirtualJoystick"/> class.
    /// </summary>
    public delegate void FlickedEventHandler(Vector2 inputVector);

    private static void FlickedTrampoline(object delegateObj, NativeVariantPtrArgs args, out godot_variant ret)
    {
        Callable.ThrowIfArgCountMismatch(args, 1);
        ((FlickedEventHandler)delegateObj)(VariantUtils.ConvertTo<Vector2>(args[0]));
        ret = default;
    }

    /// <summary>
    /// <para>Emitted when the tip moved outside the deadzone and the joystick is released. The <c>inputVector</c> contains the last input direction and strength before release. Its length is between <c>0.0</c> and <c>1.0</c>.</para>
    /// </summary>
    public unsafe event FlickedEventHandler Flicked
    {
        add => Connect(SignalName.Flicked, Callable.CreateWithUnsafeTrampoline(value, &FlickedTrampoline));
        remove => Disconnect(SignalName.Flicked, Callable.CreateWithUnsafeTrampoline(value, &FlickedTrampoline));
    }

    protected void EmitSignalFlicked(Vector2 inputVector)
    {
        EmitSignal(SignalName.Flicked, inputVector);
    }

    /// <summary>
    /// <para>Emitted when the tip enters the deadzone after being outside of it.</para>
    /// </summary>
    public event Action FlickCanceled
    {
        add => Connect(SignalName.FlickCanceled, Callable.From(value));
        remove => Disconnect(SignalName.FlickCanceled, Callable.From(value));
    }

    protected void EmitSignalFlickCanceled()
    {
        EmitSignal(SignalName.FlickCanceled);
    }

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_pressed = "Pressed";

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_tapped = "Tapped";

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_released = "Released";

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_flicked = "Flicked";

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_flick_canceled = "FlickCanceled";

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
        if (signal == SignalName.Pressed)
        {
            if (HasGodotClassSignal(SignalProxyName_pressed.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        if (signal == SignalName.Tapped)
        {
            if (HasGodotClassSignal(SignalProxyName_tapped.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        if (signal == SignalName.Released)
        {
            if (HasGodotClassSignal(SignalProxyName_released.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        if (signal == SignalName.Flicked)
        {
            if (HasGodotClassSignal(SignalProxyName_flicked.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        if (signal == SignalName.FlickCanceled)
        {
            if (HasGodotClassSignal(SignalProxyName_flick_canceled.NativeValue.DangerousSelfRef))
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
        /// <summary>
        /// Cached name for the 'joystick_mode' property.
        /// </summary>
        public static readonly StringName JoystickMode = "joystick_mode";
        /// <summary>
        /// Cached name for the 'joystick_size' property.
        /// </summary>
        public static readonly StringName JoystickSize = "joystick_size";
        /// <summary>
        /// Cached name for the 'tip_size' property.
        /// </summary>
        public static readonly StringName TipSize = "tip_size";
        /// <summary>
        /// Cached name for the 'deadzone_ratio' property.
        /// </summary>
        public static readonly StringName DeadzoneRatio = "deadzone_ratio";
        /// <summary>
        /// Cached name for the 'clampzone_ratio' property.
        /// </summary>
        public static readonly StringName ClampzoneRatio = "clampzone_ratio";
        /// <summary>
        /// Cached name for the 'initial_offset_ratio' property.
        /// </summary>
        public static readonly StringName InitialOffsetRatio = "initial_offset_ratio";
        /// <summary>
        /// Cached name for the 'action_left' property.
        /// </summary>
        public static readonly StringName ActionLeft = "action_left";
        /// <summary>
        /// Cached name for the 'action_right' property.
        /// </summary>
        public static readonly StringName ActionRight = "action_right";
        /// <summary>
        /// Cached name for the 'action_up' property.
        /// </summary>
        public static readonly StringName ActionUp = "action_up";
        /// <summary>
        /// Cached name for the 'action_down' property.
        /// </summary>
        public static readonly StringName ActionDown = "action_down";
        /// <summary>
        /// Cached name for the 'visibility_mode' property.
        /// </summary>
        public static readonly StringName VisibilityMode = "visibility_mode";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : Control.MethodName
    {
        /// <summary>
        /// Cached name for the 'set_joystick_mode' method.
        /// </summary>
        public static readonly StringName SetJoystickMode = "set_joystick_mode";
        /// <summary>
        /// Cached name for the 'get_joystick_mode' method.
        /// </summary>
        public static readonly StringName GetJoystickMode = "get_joystick_mode";
        /// <summary>
        /// Cached name for the 'set_joystick_size' method.
        /// </summary>
        public static readonly StringName SetJoystickSize = "set_joystick_size";
        /// <summary>
        /// Cached name for the 'get_joystick_size' method.
        /// </summary>
        public static readonly StringName GetJoystickSize = "get_joystick_size";
        /// <summary>
        /// Cached name for the 'set_tip_size' method.
        /// </summary>
        public static readonly StringName SetTipSize = "set_tip_size";
        /// <summary>
        /// Cached name for the 'get_tip_size' method.
        /// </summary>
        public static readonly StringName GetTipSize = "get_tip_size";
        /// <summary>
        /// Cached name for the 'set_deadzone_ratio' method.
        /// </summary>
        public static readonly StringName SetDeadzoneRatio = "set_deadzone_ratio";
        /// <summary>
        /// Cached name for the 'get_deadzone_ratio' method.
        /// </summary>
        public static readonly StringName GetDeadzoneRatio = "get_deadzone_ratio";
        /// <summary>
        /// Cached name for the 'set_clampzone_ratio' method.
        /// </summary>
        public static readonly StringName SetClampzoneRatio = "set_clampzone_ratio";
        /// <summary>
        /// Cached name for the 'get_clampzone_ratio' method.
        /// </summary>
        public static readonly StringName GetClampzoneRatio = "get_clampzone_ratio";
        /// <summary>
        /// Cached name for the 'set_initial_offset_ratio' method.
        /// </summary>
        public static readonly StringName SetInitialOffsetRatio = "set_initial_offset_ratio";
        /// <summary>
        /// Cached name for the 'get_initial_offset_ratio' method.
        /// </summary>
        public static readonly StringName GetInitialOffsetRatio = "get_initial_offset_ratio";
        /// <summary>
        /// Cached name for the 'set_action_left' method.
        /// </summary>
        public static readonly StringName SetActionLeft = "set_action_left";
        /// <summary>
        /// Cached name for the 'get_action_left' method.
        /// </summary>
        public static readonly StringName GetActionLeft = "get_action_left";
        /// <summary>
        /// Cached name for the 'set_action_right' method.
        /// </summary>
        public static readonly StringName SetActionRight = "set_action_right";
        /// <summary>
        /// Cached name for the 'get_action_right' method.
        /// </summary>
        public static readonly StringName GetActionRight = "get_action_right";
        /// <summary>
        /// Cached name for the 'set_action_up' method.
        /// </summary>
        public static readonly StringName SetActionUp = "set_action_up";
        /// <summary>
        /// Cached name for the 'get_action_up' method.
        /// </summary>
        public static readonly StringName GetActionUp = "get_action_up";
        /// <summary>
        /// Cached name for the 'set_action_down' method.
        /// </summary>
        public static readonly StringName SetActionDown = "set_action_down";
        /// <summary>
        /// Cached name for the 'get_action_down' method.
        /// </summary>
        public static readonly StringName GetActionDown = "get_action_down";
        /// <summary>
        /// Cached name for the 'set_visibility_mode' method.
        /// </summary>
        public static readonly StringName SetVisibilityMode = "set_visibility_mode";
        /// <summary>
        /// Cached name for the 'get_visibility_mode' method.
        /// </summary>
        public static readonly StringName GetVisibilityMode = "get_visibility_mode";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : Control.SignalName
    {
        /// <summary>
        /// Cached name for the 'pressed' signal.
        /// </summary>
        public static readonly StringName Pressed = "pressed";
        /// <summary>
        /// Cached name for the 'tapped' signal.
        /// </summary>
        public static readonly StringName Tapped = "tapped";
        /// <summary>
        /// Cached name for the 'released' signal.
        /// </summary>
        public static readonly StringName Released = "released";
        /// <summary>
        /// Cached name for the 'flicked' signal.
        /// </summary>
        public static readonly StringName Flicked = "flicked";
        /// <summary>
        /// Cached name for the 'flick_canceled' signal.
        /// </summary>
        public static readonly StringName FlickCanceled = "flick_canceled";
    }
}
