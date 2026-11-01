namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>The <see cref="Godot.Input"/> singleton handles key presses, mouse buttons and movement, gamepads, and input actions. Actions and their events can be set in the <b>Input Map</b> tab in <b>Project &gt; Project Settings</b>, or with the <see cref="Godot.InputMap"/> class.</para>
/// <para><b>Note:</b> <see cref="Godot.Input"/>'s methods reflect the global input state and are not affected by <see cref="Godot.Control.AcceptEvent()"/> or <see cref="Godot.Viewport.SetInputAsHandled()"/>, as those methods only deal with the way input is propagated in the <see cref="Godot.SceneTree"/>.</para>
/// </summary>
[GodotClassName("Input")]
public partial class InputInstance : GodotObject
{
    /// <summary>
    /// <para>Controls the mouse mode.</para>
    /// </summary>
    public Input.MouseModeEnum MouseMode
    {
        get
        {
            return GetMouseMode();
        }
        set
        {
            SetMouseMode(value);
        }
    }

    /// <summary>
    /// <para>If <see langword="true"/>, similar input events sent by the operating system are accumulated. When input accumulation is enabled, all input events generated during a frame will be merged and emitted when the frame is done rendering. Therefore, this limits the number of input method calls per second to the rendering FPS.</para>
    /// <para>Input accumulation can be disabled to get slightly more precise/reactive input at the cost of increased CPU usage. In applications where drawing freehand lines is required, input accumulation should generally be disabled while the user is drawing the line to get results that closely follow the actual input.</para>
    /// <para><b>Note:</b> Input accumulation is <i>enabled</i> by default.</para>
    /// </summary>
    public bool UseAccumulatedInput
    {
        get
        {
            return IsUsingAccumulatedInput();
        }
        set
        {
            SetUseAccumulatedInput(value);
        }
    }

    /// <summary>
    /// <para>If <see langword="true"/>, sends mouse input events when tapping or swiping on the touchscreen. See also <c>ProjectSettings.input_devices/pointing/emulate_mouse_from_touch</c>.</para>
    /// </summary>
    public bool EmulateMouseFromTouch
    {
        get
        {
            return IsEmulatingMouseFromTouch();
        }
        set
        {
            SetEmulateMouseFromTouch(value);
        }
    }

    /// <summary>
    /// <para>If <see langword="true"/>, sends touch input events when clicking or dragging the mouse. See also <c>ProjectSettings.input_devices/pointing/emulate_touch_from_mouse</c>.</para>
    /// </summary>
    public bool EmulateTouchFromMouse
    {
        get
        {
            return IsEmulatingTouchFromMouse();
        }
        set
        {
            SetEmulateTouchFromMouse(value);
        }
    }

    /// <summary>
    /// <para>If <see langword="true"/>, joypad input (including motion sensors) and LED light changes will be ignored and joypad vibration will be stopped when the application is not focused.</para>
    /// </summary>
    public bool IgnoreJoypadOnUnfocusedApplication
    {
        get
        {
            return IsIgnoringJoypadOnUnfocusedApplication();
        }
        set
        {
            SetIgnoreJoypadOnUnfocusedApplication(value);
        }
    }

    private static readonly System.Type CachedType = typeof(InputInstance);

    private static readonly StringName NativeName = "Input";

    internal InputInstance() : this(false)
    {
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: false);
        }
    }

    internal InputInstance(IntPtr ptr) : this(false)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: false);
        }
    }

    internal InputInstance(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsAnythingPressed, 36873697ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if any action, key, joypad button, or mouse button is being pressed. This will also return <see langword="true"/> if any action is simulated via code by calling <see cref="Godot.InputInstance.ActionPress(StringName, float)"/>.</para>
    /// </summary>
    public bool IsAnythingPressed()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind0, GodotObject.GetPtr(this)).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsKeyPressed, 1938909964ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if you are pressing the Latin key in the current keyboard layout. You can pass a <see cref="Godot.Key"/> constant.</para>
    /// <para><see cref="Godot.InputInstance.IsKeyPressed(Key)"/> is only recommended over <see cref="Godot.InputInstance.IsPhysicalKeyPressed(Key)"/> in non-game applications. This ensures that shortcut keys behave as expected depending on the user's keyboard layout, as keyboard shortcuts are generally dependent on the keyboard layout in non-game applications. If in doubt, use <see cref="Godot.InputInstance.IsPhysicalKeyPressed(Key)"/>.</para>
    /// <para><b>Note:</b> Due to keyboard ghosting, <see cref="Godot.InputInstance.IsKeyPressed(Key)"/> may return <see langword="false"/> even if one of the action's keys is pressed. See <a href="$DOCS_URL/tutorials/inputs/input_examples.html#keyboard-events">Input examples</a> in the documentation for more information.</para>
    /// <para><b>Note:</b> If you want to check if a key was just pressed by using its keycode, use Godot's input action system with <see cref="Godot.InputInstance.IsActionJustPressed(StringName, bool)"/> or use the <see cref="Godot.Node._Input(InputEvent)"/> method like this instead:</para>
    /// <para><code>
    /// public override void _Input(InputEvent @event)
    /// {
    /// 	if (@event is InputEventKey eventKey &amp;&amp; !eventKey.IsEcho() &amp;&amp; eventKey.Pressed &amp;&amp; eventKey.Keycode == Key.Space)
    /// 	{
    /// 		// Your code here.
    /// 	}
    /// }
    /// </code></para>
    /// </summary>
    public bool IsKeyPressed(Key keycode)
    {
        bool ret = NativeCalls.godot_icall_1_86(MethodBind1, GodotObject.GetPtr(this), (int)keycode).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsPhysicalKeyPressed, 1938909964ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if you are pressing the key in the physical location on the 101/102-key US QWERTY keyboard. You can pass a <see cref="Godot.Key"/> constant.</para>
    /// <para><see cref="Godot.InputInstance.IsPhysicalKeyPressed(Key)"/> is recommended over <see cref="Godot.InputInstance.IsKeyPressed(Key)"/> for in-game actions, as it will make W/A/S/D layouts work regardless of the user's keyboard layout. <see cref="Godot.InputInstance.IsPhysicalKeyPressed(Key)"/> will also ensure that the top row number keys work on any keyboard layout. If in doubt, use <see cref="Godot.InputInstance.IsPhysicalKeyPressed(Key)"/>.</para>
    /// <para><b>Note:</b> Due to keyboard ghosting, <see cref="Godot.InputInstance.IsPhysicalKeyPressed(Key)"/> may return <see langword="false"/> even if one of the action's keys is pressed. See <a href="$DOCS_URL/tutorials/inputs/input_examples.html#keyboard-events">Input examples</a> in the documentation for more information.</para>
    /// <para><b>Note:</b> If you want to check if a key was just pressed by using its physical keycode, use Godot's input action system with <see cref="Godot.InputInstance.IsActionJustPressed(StringName, bool)"/> or use the <see cref="Godot.Node._Input(InputEvent)"/> method like this instead:</para>
    /// <para><code>
    /// public override void _Input(InputEvent @event)
    /// {
    /// 	if (@event is InputEventKey eventKey &amp;&amp; !eventKey.IsEcho() &amp;&amp; eventKey.Pressed &amp;&amp; eventKey.PhysicalKeycode == Key.Space)
    /// 	{
    /// 		// Your code here.
    /// 	}
    /// }
    /// </code></para>
    /// </summary>
    public bool IsPhysicalKeyPressed(Key keycode)
    {
        bool ret = NativeCalls.godot_icall_1_86(MethodBind2, GodotObject.GetPtr(this), (int)keycode).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsKeyLabelPressed, 1938909964ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if you are pressing the key with the <paramref name="keycode"/> printed on it. You can pass a <see cref="Godot.Key"/> constant or any Unicode character code.</para>
    /// <para><b>Note:</b> If you want to check if a key was just pressed by using its label, use Godot's input action system with <see cref="Godot.InputInstance.IsActionJustPressed(StringName, bool)"/> or use the <see cref="Godot.Node._Input(InputEvent)"/> method like this instead:</para>
    /// <para><code>
    /// public override void _Input(InputEvent @event)
    /// {
    /// 	if (@event is InputEventKey eventKey &amp;&amp; !eventKey.IsEcho() &amp;&amp; eventKey.Pressed &amp;&amp; eventKey.KeyLabel == Key.Space)
    /// 	{
    /// 		// Your code here.
    /// 	}
    /// }
    /// </code></para>
    /// </summary>
    public bool IsKeyLabelPressed(Key keycode)
    {
        bool ret = NativeCalls.godot_icall_1_86(MethodBind3, GodotObject.GetPtr(this), (int)keycode).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsMouseButtonPressed, 1821097125ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if you are pressing the mouse button specified with <see cref="Godot.MouseButton"/>.</para>
    /// <para><b>Note:</b> If you want to check if a mouse button was just pressed, use Godot's input action system with <see cref="Godot.InputInstance.IsActionJustPressed(StringName, bool)"/> or use the <see cref="Godot.Node._Input(InputEvent)"/> method like this instead:</para>
    /// <para><code>
    /// public override void _Input(InputEvent @event)
    /// {
    /// 	if (@event is InputEventMouseButton eventMouseButton &amp;&amp; eventMouseButton.Pressed &amp;&amp; eventMouseButton.ButtonIndex == MouseButton.Left)
    /// 	{
    /// 		// Your code here.
    /// 	}
    /// }
    /// </code></para>
    /// </summary>
    public bool IsMouseButtonPressed(MouseButton button)
    {
        bool ret = NativeCalls.godot_icall_1_86(MethodBind4, GodotObject.GetPtr(this), (int)button).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsJoyButtonPressed, 787208542ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if you are pressing the joypad button at index <paramref name="button"/>.</para>
    /// <para><b>Note:</b> If you want to check if a joypad button was just pressed, use Godot's input action system with <see cref="Godot.InputInstance.IsActionJustPressed(StringName, bool)"/> or use the <see cref="Godot.Node._Input(InputEvent)"/> method like this instead:</para>
    /// <para><code>
    /// public override void _Input(InputEvent @event)
    /// {
    /// 	if (@event is InputEventJoypadButton eventButton &amp;&amp; eventButton.Pressed &amp;&amp; eventButton.ButtonIndex == JoyButton.A)
    /// 	{
    /// 		// Your code here.
    /// 	}
    /// }
    /// </code></para>
    /// </summary>
    public bool IsJoyButtonPressed(int device, JoyButton button)
    {
        bool ret = NativeCalls.godot_icall_2_40(MethodBind5, GodotObject.GetPtr(this), device, (int)button).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsActionPressed, 1558498928ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if you are pressing the action event.</para>
    /// <para>If <paramref name="exactMatch"/> is <see langword="false"/>, it ignores additional input modifiers for <see cref="Godot.InputEventKey"/> and <see cref="Godot.InputEventMouseButton"/> events, and the direction for <see cref="Godot.InputEventJoypadMotion"/> events.</para>
    /// <para><b>Note:</b> Due to keyboard ghosting, <see cref="Godot.InputInstance.IsActionPressed(StringName, bool)"/> may return <see langword="false"/> even if one of the action's keys is pressed. See <a href="$DOCS_URL/tutorials/inputs/input_examples.html#keyboard-events">Input examples</a> in the documentation for more information.</para>
    /// </summary>
    public bool IsActionPressed(StringName action, bool exactMatch = false)
    {
        bool ret = NativeCalls.godot_icall_2_782(MethodBind6, GodotObject.GetPtr(this), (godot_string_name)(action?.NativeValue ?? default), exactMatch.ToGodotBool()).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsActionJustPressed, 1558498928ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> when the user has <i>started</i> pressing the action event in the current frame or physics tick. It will only return <see langword="true"/> on the frame or tick that the user pressed down the button.</para>
    /// <para>This is useful for code that needs to run only once when an action is pressed, instead of every frame while it's pressed.</para>
    /// <para>If <paramref name="exactMatch"/> is <see langword="false"/>, it ignores additional input modifiers for <see cref="Godot.InputEventKey"/> and <see cref="Godot.InputEventMouseButton"/> events, and the direction for <see cref="Godot.InputEventJoypadMotion"/> events.</para>
    /// <para><b>Note:</b> Returning <see langword="true"/> does not imply that the action is <i>still</i> pressed. An action can be pressed and released again rapidly, and <see langword="true"/> will still be returned so as not to miss input.</para>
    /// <para><b>Note:</b> Due to keyboard ghosting, <see cref="Godot.InputInstance.IsActionJustPressed(StringName, bool)"/> may return <see langword="false"/> even if one of the action's keys is pressed. See <a href="$DOCS_URL/tutorials/inputs/input_examples.html#keyboard-events">Input examples</a> in the documentation for more information.</para>
    /// <para><b>Note:</b> During input handling (e.g. <see cref="Godot.Node._Input(InputEvent)"/>), use <see cref="Godot.InputEvent.IsActionPressed(StringName, bool, bool)"/> instead to query the action state of the current event. See also <see cref="Godot.InputInstance.IsActionJustPressedByEvent(StringName, InputEvent, bool)"/>.</para>
    /// </summary>
    public bool IsActionJustPressed(StringName action, bool exactMatch = false)
    {
        bool ret = NativeCalls.godot_icall_2_782(MethodBind7, GodotObject.GetPtr(this), (godot_string_name)(action?.NativeValue ?? default), exactMatch.ToGodotBool()).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind8 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsActionJustReleased, 1558498928ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> when the user <i>stops</i> pressing the action event in the current frame or physics tick. It will only return <see langword="true"/> on the frame or tick that the user releases the button.</para>
    /// <para><b>Note:</b> Returning <see langword="true"/> does not imply that the action is <i>still</i> not pressed. An action can be released and pressed again rapidly, and <see langword="true"/> will still be returned so as not to miss input.</para>
    /// <para>If <paramref name="exactMatch"/> is <see langword="false"/>, it ignores additional input modifiers for <see cref="Godot.InputEventKey"/> and <see cref="Godot.InputEventMouseButton"/> events, and the direction for <see cref="Godot.InputEventJoypadMotion"/> events.</para>
    /// <para><b>Note:</b> During input handling (e.g. <see cref="Godot.Node._Input(InputEvent)"/>), use <see cref="Godot.InputEvent.IsActionReleased(StringName, bool)"/> instead to query the action state of the current event. See also <see cref="Godot.InputInstance.IsActionJustReleasedByEvent(StringName, InputEvent, bool)"/>.</para>
    /// </summary>
    public bool IsActionJustReleased(StringName action, bool exactMatch = false)
    {
        bool ret = NativeCalls.godot_icall_2_782(MethodBind8, GodotObject.GetPtr(this), (godot_string_name)(action?.NativeValue ?? default), exactMatch.ToGodotBool()).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind9 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsActionJustPressedByEvent, 551972873ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> when the user has <i>started</i> pressing the action event in the current frame or physics tick, and the first event that triggered action press in the current frame/physics tick was <paramref name="event"/>. It will only return <see langword="true"/> on the frame or tick that the user pressed down the button.</para>
    /// <para>This is useful for code that needs to run only once when an action is pressed, and the action is processed during input handling (e.g. <see cref="Godot.Node._Input(InputEvent)"/>).</para>
    /// <para>If <paramref name="exactMatch"/> is <see langword="false"/>, it ignores additional input modifiers for <see cref="Godot.InputEventKey"/> and <see cref="Godot.InputEventMouseButton"/> events, and the direction for <see cref="Godot.InputEventJoypadMotion"/> events.</para>
    /// <para><b>Note:</b> Returning <see langword="true"/> does not imply that the action is <i>still</i> pressed. An action can be pressed and released again rapidly, and <see langword="true"/> will still be returned so as not to miss input.</para>
    /// <para><b>Note:</b> Due to keyboard ghosting, <see cref="Godot.InputInstance.IsActionJustPressed(StringName, bool)"/> may return <see langword="false"/> even if one of the action's keys is pressed. See <a href="$DOCS_URL/tutorials/inputs/input_examples.html#keyboard-events">Input examples</a> in the documentation for more information.</para>
    /// </summary>
    public bool IsActionJustPressedByEvent(StringName action, InputEvent @event, bool exactMatch = false)
    {
        bool ret = NativeCalls.godot_icall_3_783(MethodBind9, GodotObject.GetPtr(this), (godot_string_name)(action?.NativeValue ?? default), GodotObject.GetPtr(@event), exactMatch.ToGodotBool()).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind10 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsActionJustReleasedByEvent, 551972873ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> when the user <i>stops</i> pressing the action event in the current frame or physics tick, and the first event that triggered action release in the current frame/physics tick was <paramref name="event"/>. It will only return <see langword="true"/> on the frame or tick that the user releases the button.</para>
    /// <para>This is useful when an action is processed during input handling (e.g. <see cref="Godot.Node._Input(InputEvent)"/>).</para>
    /// <para><b>Note:</b> Returning <see langword="true"/> does not imply that the action is <i>still</i> not pressed. An action can be released and pressed again rapidly, and <see langword="true"/> will still be returned so as not to miss input.</para>
    /// <para>If <paramref name="exactMatch"/> is <see langword="false"/>, it ignores additional input modifiers for <see cref="Godot.InputEventKey"/> and <see cref="Godot.InputEventMouseButton"/> events, and the direction for <see cref="Godot.InputEventJoypadMotion"/> events.</para>
    /// </summary>
    public bool IsActionJustReleasedByEvent(StringName action, InputEvent @event, bool exactMatch = false)
    {
        bool ret = NativeCalls.godot_icall_3_783(MethodBind10, GodotObject.GetPtr(this), (godot_string_name)(action?.NativeValue ?? default), GodotObject.GetPtr(@event), exactMatch.ToGodotBool()).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind11 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetActionStrength, 801543509ul);

    /// <summary>
    /// <para>Returns a value between <c>0.0</c> and <c>1.0</c> representing the intensity of the given action. In a joypad, for example, the further away the axis (analog sticks or L2, R2 triggers) is from the dead zone, the closer the value will be to <c>1.0</c>. If the action is mapped to a control that has no axis such as the keyboard, the value returned will be <c>0.0</c> or <c>1.0</c>.</para>
    /// <para>If <paramref name="exactMatch"/> is <see langword="false"/>, it ignores additional input modifiers for <see cref="Godot.InputEventKey"/> and <see cref="Godot.InputEventMouseButton"/> events, and the direction for <see cref="Godot.InputEventJoypadMotion"/> events.</para>
    /// </summary>
    public float GetActionStrength(StringName action, bool exactMatch = false)
    {
        float ret = NativeCalls.godot_icall_2_784(MethodBind11, GodotObject.GetPtr(this), (godot_string_name)(action?.NativeValue ?? default), exactMatch.ToGodotBool());
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind12 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetActionRawStrength, 801543509ul);

    /// <summary>
    /// <para>Returns a value between <c>0.0</c> and <c>1.0</c> representing the raw intensity of the given action, ignoring the action's deadzone. In most cases, you should use <see cref="Godot.InputInstance.GetActionStrength(StringName, bool)"/> instead.</para>
    /// <para>If <paramref name="exactMatch"/> is <see langword="false"/>, it ignores additional input modifiers for <see cref="Godot.InputEventKey"/> and <see cref="Godot.InputEventMouseButton"/> events, and the direction for <see cref="Godot.InputEventJoypadMotion"/> events.</para>
    /// </summary>
    public float GetActionRawStrength(StringName action, bool exactMatch = false)
    {
        float ret = NativeCalls.godot_icall_2_784(MethodBind12, GodotObject.GetPtr(this), (godot_string_name)(action?.NativeValue ?? default), exactMatch.ToGodotBool());
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind13 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetAxis, 1958752504ul);

    /// <summary>
    /// <para>Returns axis input value by specifying two actions, one negative and one positive.</para>
    /// <para>This is a shorthand for writing <c>Input.get_action_strength("positive_action") - Input.get_action_strength("negative_action")</c>.</para>
    /// </summary>
    public float GetAxis(StringName negativeAction, StringName positiveAction)
    {
        float ret = NativeCalls.godot_icall_2_785(MethodBind13, GodotObject.GetPtr(this), (godot_string_name)(negativeAction?.NativeValue ?? default), (godot_string_name)(positiveAction?.NativeValue ?? default));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind14 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetVector, 2479607902ul);

    /// <summary>
    /// <para>Returns an input vector by specifying four actions for the positive and negative X and Y axes.</para>
    /// <para>This method is useful when getting vector input, such as from a joystick, directional pad, arrows, or WASD. The vector has its length limited to <c>1.0</c> and has a circular deadzone, which is useful for using vector input as movement.</para>
    /// <para>By default, the deadzone is automatically calculated from the average of the action deadzones. However, you can override the deadzone to be whatever you want (on the range of <c>0.0</c> to <c>1.0</c>).</para>
    /// </summary>
    public Vector2 GetVector(StringName negativeX, StringName positiveX, StringName negativeY, StringName positiveY, float deadzone = -1.0f)
    {
        Vector2 ret = NativeCalls.godot_icall_5_786(MethodBind14, GodotObject.GetPtr(this), (godot_string_name)(negativeX?.NativeValue ?? default), (godot_string_name)(positiveX?.NativeValue ?? default), (godot_string_name)(negativeY?.NativeValue ?? default), (godot_string_name)(positiveY?.NativeValue ?? default), deadzone);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind15 = ClassDB_get_method_with_compatibility(NativeName, MethodName.AddJoyMapping, 1168363258ul);

    /// <summary>
    /// <para>Adds a new joypad mapping entry (in SDL format) to the mapping database, and optionally updates the already connected devices.</para>
    /// <para><b>Note:</b> See <a href="https://wiki.libsdl.org/SDL3/SDL_AddGamepadMapping#remarks">SDL documentation</a> for more information about the SDL controller mapping format.</para>
    /// </summary>
    public void AddJoyMapping(string mapping, bool updateExisting = false)
    {
        NativeCalls.godot_icall_2_515(MethodBind15, GodotObject.GetPtr(this), mapping, updateExisting.ToGodotBool());
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind16 = ClassDB_get_method_with_compatibility(NativeName, MethodName.RemoveJoyMapping, 83702148ul);

    /// <summary>
    /// <para>Removes all mappings from the internal database that match the given GUID. All currently connected joypads that use this GUID will become unmapped.</para>
    /// <para>On Android, Godot will map to an internal fallback mapping.</para>
    /// </summary>
    public void RemoveJoyMapping(string guid)
    {
        NativeCalls.godot_icall_1_57(MethodBind16, GodotObject.GetPtr(this), guid);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind17 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsJoyKnown, 3067735520ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if the system knows the specified device. This means that it sets all button and axis indices. Unknown joypads are not expected to match these constants, but you can still retrieve events from them.</para>
    /// </summary>
    public bool IsJoyKnown(int device)
    {
        bool ret = NativeCalls.godot_icall_1_86(MethodBind17, GodotObject.GetPtr(this), device).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind18 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetJoyAxis, 4063175957ul);

    /// <summary>
    /// <para>Returns the current value of the joypad axis at index <paramref name="axis"/>.</para>
    /// </summary>
    public float GetJoyAxis(int device, JoyAxis axis)
    {
        float ret = NativeCalls.godot_icall_2_112(MethodBind18, GodotObject.GetPtr(this), device, (int)axis);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind19 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetJoyName, 990163283ul);

    /// <summary>
    /// <para>Returns the name of the joypad at the specified device index, e.g. <c>PS4 Controller</c>. Godot uses the <a href="https://github.com/gabomdq/SDL_GameControllerDB">SDL game controller database</a> to determine gamepad names.</para>
    /// </summary>
    public string GetJoyName(int device)
    {
        string ret = NativeCalls.godot_icall_1_158(MethodBind19, GodotObject.GetPtr(this), device);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind20 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetJoyGuid, 844755477ul);

    /// <summary>
    /// <para>Returns an SDL-compatible device GUID on platforms that use gamepad remapping, e.g. <c>030000004c050000c405000000010000</c>. Returns an empty string if it cannot be found. Godot uses SDL's internal mappings, supplemented by community-contributed mappings, to determine gamepad names and mappings based on this GUID.</para>
    /// </summary>
    public string GetJoyGuid(int device)
    {
        string ret = NativeCalls.godot_icall_1_158(MethodBind20, GodotObject.GetPtr(this), device);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind21 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetJoyInfo, 3485342025ul);

    /// <summary>
    /// <para>Returns a dictionary with extra platform-specific information about the device, e.g. the raw gamepad name from the OS or the Steam Input index.</para>
    /// <para>On Windows, Linux, macOS, and iOS, the dictionary contains the following fields:</para>
    /// <para><c>raw_name</c>: The name of the controller as it came from the OS, before getting renamed by the controller database.</para>
    /// <para><c>vendor_id</c>: The USB vendor ID of the device.</para>
    /// <para><c>product_id</c>: The USB product ID of the device.</para>
    /// <para><c>serial_number</c>: The serial number of the device. This key won't be present if the serial number is unavailable.</para>
    /// <para>The dictionary can also include the following fields under selected platforms:</para>
    /// <para><c>steam_input_index</c>: The Steam Input gamepad index (Windows, Linux, and macOS only). If the device is not a Steam Input device this key won't be present.</para>
    /// <para><c>xinput_index</c>: The index of the controller in the XInput system (Windows only). This key won't be present for devices not handled by XInput.</para>
    /// <para><b>Note:</b> The returned dictionary is always empty on Android and Web.</para>
    /// </summary>
    public Godot.Collections.Dictionary GetJoyInfo(int device)
    {
        Godot.Collections.Dictionary ret = NativeCalls.godot_icall_1_335(MethodBind21, GodotObject.GetPtr(this), device);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind22 = ClassDB_get_method_with_compatibility(NativeName, MethodName.ShouldIgnoreDevice, 2522259332ul);

    /// <summary>
    /// <para>Queries whether an input device should be ignored or not. Devices can be ignored by setting the environment variable <c>SDL_GAMECONTROLLER_IGNORE_DEVICES</c>. See <a href="https://wiki.libsdl.org/SDL3/SDL_HINT_GAMECONTROLLER_IGNORE_DEVICES">SDL documentation</a> for more information.</para>
    /// <para><b>Note:</b> Some 3rd party tools can contribute to the list of ignored devices. For example, <i>SteamInput</i> creates virtual devices from physical devices for remapping purposes. To avoid handling the same input device twice, the original device is added to the ignore list.</para>
    /// </summary>
    public bool ShouldIgnoreDevice(int vendorId, int productId)
    {
        bool ret = NativeCalls.godot_icall_2_40(MethodBind22, GodotObject.GetPtr(this), vendorId, productId).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind23 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetConnectedJoypads, 2915620761ul);

    /// <summary>
    /// <para>Returns an <see cref="Godot.Collections.Array"/> containing the device IDs of all currently connected joypads.</para>
    /// <para><b>Note:</b> The order of connected joypads can not be guaranteed to be the same after a project and/or the editor is restarted, because Godot doesn't save the order of joypad connections. Joypads are registered in the order they are discovered by Godot.</para>
    /// </summary>
    public Godot.Collections.Array<int> GetConnectedJoypads()
    {
        Godot.Collections.Array<int> ret = new Godot.Collections.Array<int>(NativeCalls.godot_icall_0_146(MethodBind23, GodotObject.GetPtr(this)));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind24 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetJoyVibrationStrength, 3114997196ul);

    /// <summary>
    /// <para>Returns the strength of the joypad vibration: x is the strength of the weak motor, and y is the strength of the strong motor.</para>
    /// <para><b>Note:</b> This method returns the same values that were passed to <see cref="Godot.InputInstance.StartJoyVibration(int, float, float, float)"/>, and these values do <b>not</b> change when the joypad's vibration runs out, they only get reset after a call to <see cref="Godot.InputInstance.StopJoyVibration(int)"/>.</para>
    /// <para>If you want to check if a joypad is still vibrating, use <see cref="Godot.InputInstance.IsJoyVibrating(int)"/> instead.</para>
    /// </summary>
    public Vector2 GetJoyVibrationStrength(int device)
    {
        Vector2 ret = NativeCalls.godot_icall_1_176(MethodBind24, GodotObject.GetPtr(this), device);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind25 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetJoyVibrationDuration, 4025615559ul);

    /// <summary>
    /// <para>Returns the duration of the current vibration effect in seconds.</para>
    /// <para><b>Note:</b> This method returns the same value that was passed to <see cref="Godot.InputInstance.StartJoyVibration(int, float, float, float)"/>, and this value does <b>not</b> change when the joypad's vibration runs out, it only gets reset after a call to <see cref="Godot.InputInstance.StopJoyVibration(int)"/>.</para>
    /// <para>If you want to check if a joypad is still vibrating, use <see cref="Godot.InputInstance.IsJoyVibrating(int)"/> instead.</para>
    /// </summary>
    public float GetJoyVibrationDuration(int device)
    {
        float ret = NativeCalls.godot_icall_1_96(MethodBind25, GodotObject.GetPtr(this), device);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind26 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetJoyVibrationRemainingDuration, 4025615559ul);

    /// <summary>
    /// <para>Returns the remaining duration of the current vibration effect in seconds.</para>
    /// </summary>
    public float GetJoyVibrationRemainingDuration(int device)
    {
        float ret = NativeCalls.godot_icall_1_96(MethodBind26, GodotObject.GetPtr(this), device);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind27 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsJoyVibrating, 3067735520ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if the joypad is still vibrating after a call to <see cref="Godot.InputInstance.StartJoyVibration(int, float, float, float)"/>.</para>
    /// <para>Unlike <see cref="Godot.InputInstance.GetJoyVibrationStrength(int)"/> and <see cref="Godot.InputInstance.GetJoyVibrationDuration(int)"/>, this method returns <see langword="false"/> after the joypad's vibration runs out.</para>
    /// </summary>
    public bool IsJoyVibrating(int device)
    {
        bool ret = NativeCalls.godot_icall_1_86(MethodBind27, GodotObject.GetPtr(this), device).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind28 = ClassDB_get_method_with_compatibility(NativeName, MethodName.HasJoyVibration, 1116898809ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if the joypad supports vibration. See also <see cref="Godot.InputInstance.StartJoyVibration(int, float, float, float)"/>.</para>
    /// <para><b>Note:</b> For macOS, vibration is only supported in macOS 11 and later. When connected via USB, vibration is only supported for major brand controllers (except Xbox One and Xbox Series X/S controllers) due to macOS limitations.</para>
    /// </summary>
    public bool HasJoyVibration(int device)
    {
        bool ret = NativeCalls.godot_icall_1_86(MethodBind28, GodotObject.GetPtr(this), device).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind29 = ClassDB_get_method_with_compatibility(NativeName, MethodName.StartJoyVibration, 2576575033ul);

    /// <summary>
    /// <para>Starts vibrating the joypad. See also <see cref="Godot.InputInstance.HasJoyVibration(int)"/> and <see cref="Godot.InputInstance.IsJoyVibrating(int)"/>.</para>
    /// <para>Joypads usually come with two rumble motors, a strong and a weak one.</para>
    /// <para><paramref name="weakMagnitude"/> is the strength of the weak motor (between <c>0.0</c> and <c>1.0</c>).</para>
    /// <para><paramref name="strongMagnitude"/> is the strength of the strong motor (between <c>0.0</c> and <c>1.0</c>).</para>
    /// <para><paramref name="duration"/> is the duration of the effect in seconds (a duration of <c>0.0</c> will try to play the vibration as long as possible, which is about 65 seconds).</para>
    /// <para>The vibration can be stopped early by calling <see cref="Godot.InputInstance.StopJoyVibration(int)"/>.</para>
    /// <para>See also <see cref="Godot.InputInstance.GetJoyVibrationStrength(int)"/> and <see cref="Godot.InputInstance.GetJoyVibrationDuration(int)"/>.</para>
    /// <para><b>Note:</b> For macOS, vibration is only supported in macOS 11 and later. When connected via USB, vibration is only supported for major brand controllers (except Xbox One and Xbox Series X/S controllers) due to macOS limitations.</para>
    /// </summary>
    public void StartJoyVibration(int device, float weakMagnitude, float strongMagnitude, float duration = (float)(0))
    {
        NativeCalls.godot_icall_4_787(MethodBind29, GodotObject.GetPtr(this), device, weakMagnitude, strongMagnitude, duration);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind30 = ClassDB_get_method_with_compatibility(NativeName, MethodName.StopJoyVibration, 1286410249ul);

    /// <summary>
    /// <para>Stops the vibration of the joypad started with <see cref="Godot.InputInstance.StartJoyVibration(int, float, float, float)"/>.</para>
    /// </summary>
    public void StopJoyVibration(int device)
    {
        NativeCalls.godot_icall_1_38(MethodBind30, GodotObject.GetPtr(this), device);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind31 = ClassDB_get_method_with_compatibility(NativeName, MethodName.VibrateHandheld, 544894297ul);

    /// <summary>
    /// <para>Starts vibrating the handheld device for the specified duration in milliseconds.</para>
    /// <para><paramref name="amplitude"/> is the strength of the vibration, as a value between <c>0.0</c> and <c>1.0</c>. If set to <c>-1.0</c>, the default vibration strength of the device is used.</para>
    /// <para><b>Note:</b> This method is implemented on Android, iOS, and Web. It has no effect on other platforms.</para>
    /// <para><b>Note:</b> For Android, <see cref="Godot.InputInstance.VibrateHandheld(int, float)"/> requires enabling the <c>VIBRATE</c> permission in the export preset. Otherwise, <see cref="Godot.InputInstance.VibrateHandheld(int, float)"/> will have no effect.</para>
    /// <para><b>Note:</b> For iOS, specifying the duration is only supported in iOS 13 and later.</para>
    /// <para><b>Note:</b> For Web, the amplitude cannot be changed.</para>
    /// <para><b>Note:</b> Some web browsers such as Safari and Firefox for Android do not support <see cref="Godot.InputInstance.VibrateHandheld(int, float)"/>.</para>
    /// <para><b>Note:</b> Device settings such as vibration on/off, "do not disturb" mode or specific haptic feedback on/off may prevent <see cref="Godot.InputInstance.VibrateHandheld(int, float)"/> effects.</para>
    /// </summary>
    public void VibrateHandheld(int durationMs = 500, float amplitude = -1.0f)
    {
        NativeCalls.godot_icall_2_93(MethodBind31, GodotObject.GetPtr(this), durationMs, amplitude);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind32 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetIgnoreJoypadOnUnfocusedApplication, 2586408642ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetIgnoreJoypadOnUnfocusedApplication(bool enable)
    {
        NativeCalls.godot_icall_1_14(MethodBind32, GodotObject.GetPtr(this), enable.ToGodotBool());
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind33 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsIgnoringJoypadOnUnfocusedApplication, 36873697ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public bool IsIgnoringJoypadOnUnfocusedApplication()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind33, GodotObject.GetPtr(this)).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind34 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetGravity, 3360562783ul);

    /// <summary>
    /// <para>Returns the gravity in m/s² of the device's accelerometer sensor, if the device has one. Otherwise, the method returns <c>Vector3.ZERO</c>.</para>
    /// <para><b>Note:</b> This method only works on Android and iOS. On other platforms, it always returns <c>Vector3.ZERO</c>.</para>
    /// <para><b>Note:</b> For Android, <c>ProjectSettings.input_devices/sensors/enable_gravity</c> must be enabled.</para>
    /// </summary>
    public Vector3 GetGravity()
    {
        Vector3 ret = NativeCalls.godot_icall_0_151(MethodBind34, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind35 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetAccelerometer, 3360562783ul);

    /// <summary>
    /// <para>Returns the acceleration in m/s² of the device's accelerometer sensor, if the device has one. Otherwise, the method returns <c>Vector3.ZERO</c>.</para>
    /// <para>Note this method returns an empty <see cref="Godot.Vector3"/> when running from the editor even when your device has an accelerometer. You must export your project to a supported device to read values from the accelerometer.</para>
    /// <para><b>Note:</b> This method only works on Android and iOS. On other platforms, it always returns <c>Vector3.ZERO</c>.</para>
    /// <para><b>Note:</b> For Android, <c>ProjectSettings.input_devices/sensors/enable_accelerometer</c> must be enabled.</para>
    /// </summary>
    public Vector3 GetAccelerometer()
    {
        Vector3 ret = NativeCalls.godot_icall_0_151(MethodBind35, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind36 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMagnetometer, 3360562783ul);

    /// <summary>
    /// <para>Returns the magnetic field strength in micro-Tesla for all axes of the device's magnetometer sensor, if the device has one. Otherwise, the method returns <c>Vector3.ZERO</c>.</para>
    /// <para><b>Note:</b> This method only works on Android and iOS. On other platforms, it always returns <c>Vector3.ZERO</c>.</para>
    /// <para><b>Note:</b> For Android, <c>ProjectSettings.input_devices/sensors/enable_magnetometer</c> must be enabled.</para>
    /// </summary>
    public Vector3 GetMagnetometer()
    {
        Vector3 ret = NativeCalls.godot_icall_0_151(MethodBind36, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind37 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetGyroscope, 3360562783ul);

    /// <summary>
    /// <para>Returns the rotation rate in rad/s around a device's X, Y, and Z axes of the gyroscope sensor, if the device has one. Otherwise, the method returns <c>Vector3.ZERO</c>.</para>
    /// <para><b>Note:</b> This method only works on Android and iOS. On other platforms, it always returns <c>Vector3.ZERO</c>.</para>
    /// <para><b>Note:</b> For Android, <c>ProjectSettings.input_devices/sensors/enable_gyroscope</c> must be enabled.</para>
    /// </summary>
    public Vector3 GetGyroscope()
    {
        Vector3 ret = NativeCalls.godot_icall_0_151(MethodBind37, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind38 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetDeviceOrientation, 1222331677ul);

    /// <summary>
    /// <para>Returns the device's orientation as a <see cref="Godot.Quaternion"/>, using hardware-level sensor fusion for stable, drift-free results. If the device does not support orientation sensing, the method returns <c>Quaternion.IDENTITY</c>.</para>
    /// <para>The returned quaternion represents the rotation from the device coordinate frame to the world coordinate frame. In portrait mode, the device's coordinate system is: X right, Y up, Z towards viewer.</para>
    /// <para><b>Note:</b> This method only works on Android and iOS. On other platforms, it always returns <c>Quaternion.IDENTITY</c>.</para>
    /// <para><b>Note:</b> For Android, <c>ProjectSettings.input_devices/sensors/enable_device_orientation</c> must be enabled.</para>
    /// <para><code>
    /// var orientation := Input.get_device_orientation()
    /// var euler := orientation.get_euler()
    /// var roll := euler.z  # Device roll angle in radians.
    /// </code></para>
    /// </summary>
    public Quaternion GetDeviceOrientation()
    {
        Quaternion ret = NativeCalls.godot_icall_0_152(MethodBind38, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind39 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetJoyAccelerometer, 711720468ul);

    /// <summary>
    /// <para>Returns the acceleration, including the force of gravity, in m/s² of the joypad's accelerometer sensor, if the joypad has one and it's currently enabled. Otherwise, the method returns <c>Vector3.ZERO</c>. See also <see cref="Godot.InputInstance.GetJoyGravity(int)"/> and <see cref="Godot.InputInstance.SetJoyMotionSensorsEnabled(int, bool)"/>.</para>
    /// <para>For a joypad held in front of you, the returned axes are defined as follows:</para>
    /// <para>+X ... -X: left ... right;</para>
    /// <para>+Y ... -Y: bottom ... top;</para>
    /// <para>+Z ... -Z: farther ... closer.</para>
    /// <para>The gravity part value is measured as a vector with length of <c>9.8</c> away from the center of the Earth, which is a negative Y value.</para>
    /// <para><b>Note:</b> This feature is only supported on Windows, Linux, macOS, and iOS.</para>
    /// </summary>
    public Vector3 GetJoyAccelerometer(int device)
    {
        Vector3 ret = NativeCalls.godot_icall_1_248(MethodBind39, GodotObject.GetPtr(this), device);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind40 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetJoyGravity, 711720468ul);

    /// <summary>
    /// <para>Returns the gravity in m/s² of the joypad's accelerometer sensor, if the joypad has one and it's currently enabled. Otherwise, the method returns <c>Vector3.ZERO</c>. See also <see cref="Godot.InputInstance.GetJoyAccelerometer(int)"/> and <see cref="Godot.InputInstance.SetJoyMotionSensorsEnabled(int, bool)"/>.</para>
    /// <para>For a joypad held in front of you, the returned axes are defined as follows:</para>
    /// <para>+X ... -X: left ... right;</para>
    /// <para>+Y ... -Y: bottom ... top;</para>
    /// <para>+Z ... -Z: farther ... closer.</para>
    /// <para>The gravity part value is measured as a vector with length of <c>9.8</c> away from the center of the Earth, which is a negative Y value.</para>
    /// <para><b>Note:</b> This feature is only supported on Windows, Linux, macOS, and iOS.</para>
    /// </summary>
    public Vector3 GetJoyGravity(int device)
    {
        Vector3 ret = NativeCalls.godot_icall_1_248(MethodBind40, GodotObject.GetPtr(this), device);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind41 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetJoyGyroscope, 711720468ul);

    /// <summary>
    /// <para>Returns the rotation rate in rad/s around a joypad's X, Y, and Z axes of the gyroscope sensor, if the joypad has one and it's currently enabled. Otherwise, the method returns <c>Vector3.ZERO</c>. See also <see cref="Godot.InputInstance.SetJoyMotionSensorsEnabled(int, bool)"/>.</para>
    /// <para>The rotation is positive in the counter-clockwise direction.</para>
    /// <para>For a joypad held in front of you, the returned axes are defined as follows:</para>
    /// <para>X: Angular speed around the X axis (pitch);</para>
    /// <para>Y: Angular speed around the Y axis (yaw);</para>
    /// <para>Z: Angular speed around the Z axis (roll).</para>
    /// <para>See <see cref="Godot.InputInstance.StartJoyMotionSensorsCalibration(int)"/> for an example on how to use joypad gyroscope and gyroscope calibration in your games.</para>
    /// <para><b>Note:</b> This feature is only supported on Windows, Linux, macOS, and iOS.</para>
    /// </summary>
    public Vector3 GetJoyGyroscope(int device)
    {
        Vector3 ret = NativeCalls.godot_icall_1_248(MethodBind41, GodotObject.GetPtr(this), device);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind42 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetJoyMotionSensorsRate, 2339986948ul);

    /// <summary>
    /// <para>Returns the joypad's motion sensor rate in Hz, if the joypad has motion sensors and they're currently enabled. See also <see cref="Godot.InputInstance.SetJoyMotionSensorsEnabled(int, bool)"/>.</para>
    /// <para><b>Note:</b> This feature is only supported on Windows, Linux, macOS, and iOS.</para>
    /// </summary>
    public float GetJoyMotionSensorsRate(int device)
    {
        float ret = NativeCalls.godot_icall_1_96(MethodBind42, GodotObject.GetPtr(this), device);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind43 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsJoyMotionSensorsEnabled, 1116898809ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if the requested joypad has motion sensors (gyroscope and/or accelerometer) and they are currently enabled. See also <see cref="Godot.InputInstance.SetJoyMotionSensorsEnabled(int, bool)"/> and <see cref="Godot.InputInstance.HasJoyMotionSensors(int)"/>.</para>
    /// <para>See <see cref="Godot.InputInstance.StartJoyMotionSensorsCalibration(int)"/> for an example on how to use joypad motion sensors and calibration in your games.</para>
    /// <para><b>Note:</b> This feature is only supported on Windows, Linux, macOS, and iOS.</para>
    /// </summary>
    public bool IsJoyMotionSensorsEnabled(int device)
    {
        bool ret = NativeCalls.godot_icall_1_86(MethodBind43, GodotObject.GetPtr(this), device).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind44 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetJoyMotionSensorsEnabled, 300928843ul);

    /// <summary>
    /// <para>Enables or disables the motion sensors (gyroscope and/or accelerometer), if available, on the specified joypad.</para>
    /// <para>While the motion sensors are enabled, the gyroscope is calibrated automatically by default; see <see cref="Godot.InputInstance.SetJoyMotionSensorsAutoCalibrationEnabled(int, bool)"/>.</para>
    /// <para>See <see cref="Godot.InputInstance.StartJoyMotionSensorsCalibration(int)"/> for an example on how to use joypad motion sensors and calibration in your games.</para>
    /// <para>It's recommended to disable the motion sensors when they're no longer being used, because otherwise it might drain the controller battery faster.</para>
    /// <para><b>Note:</b> This feature is only supported on Windows, Linux, macOS, and iOS.</para>
    /// </summary>
    public void SetJoyMotionSensorsEnabled(int device, bool enable)
    {
        NativeCalls.godot_icall_2_67(MethodBind44, GodotObject.GetPtr(this), device, enable.ToGodotBool());
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind45 = ClassDB_get_method_with_compatibility(NativeName, MethodName.HasJoyMotionSensors, 1116898809ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if the joypad has motion sensors (gyroscope and/or accelerometer).</para>
    /// <para><b>Note:</b> This feature is only supported on Windows, Linux, macOS, and iOS.</para>
    /// </summary>
    public bool HasJoyMotionSensors(int device)
    {
        bool ret = NativeCalls.godot_icall_1_86(MethodBind45, GodotObject.GetPtr(this), device).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind46 = ClassDB_get_method_with_compatibility(NativeName, MethodName.StartJoyMotionSensorsCalibration, 1286410249ul);

    /// <summary>
    /// <para>Starts the process of manually calibrating the specified joypad's gyroscope, if it has one.</para>
    /// <para>Once a joypad's gyroscope has been calibrated correctly (e.g. laying still on a table without being rotated), <see cref="Godot.InputInstance.GetJoyGyroscope(int)"/> will return values close or equal to <c>Vector3.ZERO</c> when the joypad is not being rotated.</para>
    /// <para>Since the gyroscope is calibrated automatically by default (see <see cref="Godot.InputInstance.SetJoyMotionSensorsAutoCalibrationEnabled(int, bool)"/>), most games don't need to calibrate manually. If automatic calibration is enabled, it's paused while the manual calibration is in progress, and resumes when <see cref="Godot.InputInstance.StopJoyMotionSensorsCalibration(int)"/> is called.</para>
    /// <para>Here's an example of how to use joypad gyroscope and gyroscope calibration in your games:</para>
    /// <para><code>
    /// private const float GyroSensitivity = 10.0;
    /// 
    /// public override void _Ready()
    /// {
    /// 	// In this example we only use the first connected joypad (id 0).
    /// 	if (!Input.GetConnectedJoypads().Contains(0))
    /// 	{
    /// 		return;
    /// 	}
    /// 
    /// 	if (!Input.HasJoyMotionSensors(0))
    /// 	{
    /// 		return;
    /// 	}
    /// 
    /// 	// We must enable the accelerometer and the gyroscope before using them.
    /// 	Input.SetJoyMotionSensorsEnabled(0, true);
    /// 
    /// 	// (Tell the users here that they need to put their joypads on a flat surface and wait for confirmation.)
    /// 
    /// 	// Start the calibration process.
    /// 	CalibrateMotion();
    /// }
    /// 
    /// public override void _Process(double delta)
    /// {
    /// 	// Only move the object if the joypad motion sensors are calibrated.
    /// 	if (Input.IsJoyMotionSensorsCalibrated(0))
    /// 	{
    /// 		MoveObject(delta);
    /// 	}
    /// }
    /// 
    /// private async Task CalibrateMotion()
    /// {
    /// 	Input.StartJoyMotionSensorsCalibration(0);
    /// 
    /// 	// Wait for some time.
    /// 	await ToSignal(GetTree().CreateTimer(1.0), SceneTreeTimer.SignalName.Timeout);
    /// 
    /// 	Input.StopJoyMotionSensorsCalibration(0);
    /// 	// The joypad is now calibrated.
    /// }
    /// 
    /// private void MoveObject(double delta)
    /// {
    /// 	Node3D node = ... ; // Put your object here.
    /// 	Vector3 gyro = Input.GetJoyGyroscope(0);
    /// 	Vector3 rotation = node.Rotation;
    /// 	rotation.X -= -gyro.Y * GyroSensitivity * (float)delta; // Use rotation around the Y axis (yaw) here.
    /// 	rotation.Y += -gyro.X * GyroSensitivity * (float)delta; // Use rotation around the X axis (pitch) here.
    /// 	node.Rotation = rotation;
    /// }
    /// </code></para>
    /// <para><b>Note:</b> Accelerometer sensor doesn't usually require calibration.</para>
    /// <para><b>Note:</b> This feature is only supported on Windows, Linux, macOS, and iOS.</para>
    /// </summary>
    public void StartJoyMotionSensorsCalibration(int device)
    {
        NativeCalls.godot_icall_1_38(MethodBind46, GodotObject.GetPtr(this), device);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind47 = ClassDB_get_method_with_compatibility(NativeName, MethodName.StopJoyMotionSensorsCalibration, 1286410249ul);

    /// <summary>
    /// <para>Stops the manual calibration process of the specified joypad's motion sensors.</para>
    /// <para>See <see cref="Godot.InputInstance.StartJoyMotionSensorsCalibration(int)"/> for an example on how to use joypad motion sensors and calibration in your games.</para>
    /// <para><b>Note:</b> This feature is only supported on Windows, Linux, macOS, and iOS.</para>
    /// </summary>
    public void StopJoyMotionSensorsCalibration(int device)
    {
        NativeCalls.godot_icall_1_38(MethodBind47, GodotObject.GetPtr(this), device);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind48 = ClassDB_get_method_with_compatibility(NativeName, MethodName.ClearJoyMotionSensorsCalibration, 1286410249ul);

    /// <summary>
    /// <para>Clears the calibration information for the specified joypad's motion sensors, if it has any and if they were calibrated.</para>
    /// <para>See <see cref="Godot.InputInstance.StartJoyMotionSensorsCalibration(int)"/> for an example on how to use joypad motion sensors and calibration in your games.</para>
    /// <para><b>Note:</b> This feature is only supported on Windows, Linux, macOS, and iOS.</para>
    /// </summary>
    public void ClearJoyMotionSensorsCalibration(int device)
    {
        NativeCalls.godot_icall_1_38(MethodBind48, GodotObject.GetPtr(this), device);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind49 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetJoyMotionSensorsCalibration, 3485342025ul);

    /// <summary>
    /// <para>Returns the calibration information about the specified joypad's motion sensors in the form of a <see cref="Godot.Collections.Dictionary"/>, if it has any and if they have been calibrated, otherwise returns an empty <see cref="Godot.Collections.Dictionary"/>.</para>
    /// <para>The dictionary contains the following fields:</para>
    /// <para><c>gyroscope_offset</c>: average offset in gyroscope values from <c>Vector2.ZERO</c> in rad/s.</para>
    /// <para>See <see cref="Godot.InputInstance.StartJoyMotionSensorsCalibration(int)"/> for an example on how to use joypad motion sensors and calibration in your games.</para>
    /// <para><b>Note:</b> This feature is only supported on Windows, Linux, macOS, and iOS.</para>
    /// </summary>
    public Godot.Collections.Dictionary GetJoyMotionSensorsCalibration(int device)
    {
        Godot.Collections.Dictionary ret = NativeCalls.godot_icall_1_335(MethodBind49, GodotObject.GetPtr(this), device);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind50 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetJoyMotionSensorsCalibration, 64545446ul);

    /// <summary>
    /// <para>Sets the specified joypad's calibration information. See also <see cref="Godot.InputInstance.GetJoyMotionSensorsCalibration(int)"/>.</para>
    /// <para>See <see cref="Godot.InputInstance.StartJoyMotionSensorsCalibration(int)"/> for an example on how to use joypad motion sensors and calibration in your games.</para>
    /// <para><b>Note:</b> This feature is only supported on Windows, Linux, macOS, and iOS.</para>
    /// </summary>
    public void SetJoyMotionSensorsCalibration(int device, Godot.Collections.Dictionary calibrationInfo)
    {
        NativeCalls.godot_icall_2_628(MethodBind50, GodotObject.GetPtr(this), device, (godot_dictionary)(calibrationInfo ?? new()).NativeValue);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind51 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsJoyMotionSensorsCalibrated, 1116898809ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if the joypad's motion sensors have been calibrated.</para>
    /// <para>See <see cref="Godot.InputInstance.StartJoyMotionSensorsCalibration(int)"/> for an example on how to use joypad motion sensors and calibration in your games.</para>
    /// <para><b>Note:</b> This feature is only supported on Windows, Linux, macOS, and iOS.</para>
    /// </summary>
    public bool IsJoyMotionSensorsCalibrated(int device)
    {
        bool ret = NativeCalls.godot_icall_1_86(MethodBind51, GodotObject.GetPtr(this), device).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind52 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsJoyMotionSensorsCalibrating, 1116898809ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if the joypad's motion sensors are currently being manually calibrated.</para>
    /// <para>See <see cref="Godot.InputInstance.StartJoyMotionSensorsCalibration(int)"/> for an example on how to use joypad motion sensors and calibration in your games.</para>
    /// <para><b>Note:</b> This feature is only supported on Windows, Linux, macOS, and iOS.</para>
    /// </summary>
    public bool IsJoyMotionSensorsCalibrating(int device)
    {
        bool ret = NativeCalls.godot_icall_1_86(MethodBind52, GodotObject.GetPtr(this), device).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind53 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetJoyMotionSensorsAutoCalibrationEnabled, 300928843ul);

    /// <summary>
    /// <para>Enables or disables automatic calibration of the joypad's gyroscope. Automatic calibration is enabled by default, so most games don't need to call this or perform any calibration.</para>
    /// <para>While enabled, the gyroscope calibration is continuously refined whenever the joypad is detected to be held still, easing corrections in gradually. This removes the need for a dedicated calibration step in most games and keeps up with calibration drift, e.g. from the controller warming up during play.</para>
    /// <para>When automatic calibration is disabled, the last calibrated values remain in effect.</para>
    /// <para><b>Note:</b> This feature is only supported on Windows, Linux, macOS, and iOS.</para>
    /// </summary>
    public void SetJoyMotionSensorsAutoCalibrationEnabled(int device, bool enable)
    {
        NativeCalls.godot_icall_2_67(MethodBind53, GodotObject.GetPtr(this), device, enable.ToGodotBool());
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind54 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsJoyMotionSensorsAutoCalibrationEnabled, 1116898809ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if automatic calibration is enabled on the joypad's motion sensors. Automatic calibration is enabled by default. See also <see cref="Godot.InputInstance.SetJoyMotionSensorsAutoCalibrationEnabled(int, bool)"/>.</para>
    /// <para><b>Note:</b> This feature is only supported on Windows, Linux, macOS, and iOS.</para>
    /// </summary>
    public bool IsJoyMotionSensorsAutoCalibrationEnabled(int device)
    {
        bool ret = NativeCalls.godot_icall_1_86(MethodBind54, GodotObject.GetPtr(this), device).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind55 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetJoyTouchpadFingerPosition, 4135671252ul);

    /// <summary>
    /// <para>Returns the position of the specified finger on the specified touchpad on the joypad. The X and Y values, if the specified finger is touching the specified touchpad, are in the range from <c>0.0</c> to <c>1.0</c>, with <c>(0.0, 0.0)</c> representing the top-left corner of the touchpad and <c>(1.0, 1.0)</c> representing the bottom-right corner.</para>
    /// <para>If the joypad doesn't have the specified touchpad or the specified finger is not currently touching the touchpad, this method returns <c>Vector2(-1.0, -1.0)</c>.</para>
    /// <para><b>Note:</b> This feature is only supported on Windows, Linux, macOS, and iOS.</para>
    /// </summary>
    public Vector2 GetJoyTouchpadFingerPosition(int device, int finger, int touchpad = 0)
    {
        Vector2 ret = NativeCalls.godot_icall_3_642(MethodBind55, GodotObject.GetPtr(this), device, finger, touchpad);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind56 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetJoyTouchpadFingerPressure, 4212583121ul);

    /// <summary>
    /// <para>Returns the pressure of the specified finger on the specified touchpad on the joypad. The return value, if the specified finger is touching the specified touchpad, is in the range from <c>0.0</c> to <c>1.0</c>.</para>
    /// <para>If the joypad doesn't have the specified touchpad or the specified finger is not currently touching the touchpad, this method returns <c>-1.0</c>.</para>
    /// <para><b>Note:</b> This feature is only supported on Windows, Linux, macOS, and iOS.</para>
    /// </summary>
    public float GetJoyTouchpadFingerPressure(int device, int finger, int touchpad = 0)
    {
        float ret = NativeCalls.godot_icall_3_788(MethodBind56, GodotObject.GetPtr(this), device, finger, touchpad);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind57 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetJoyTouchpadFingers, 3923454890ul);

    /// <summary>
    /// <para>Returns an array of finger IDs that are currently touching the specified touchpad on the joypad. If the joypad doesn't have the specified touchpad or no fingers are currently touching this touchpad, this method returns an empty array.</para>
    /// <para><b>Note:</b> To retrieve the positions of the touchpad fingers, use <see cref="Godot.InputInstance.GetJoyTouchpadFingerPosition(int, int, int)"/>.</para>
    /// <para><b>Note:</b> This feature is only supported on Windows, Linux, macOS, and iOS.</para>
    /// </summary>
    public int[] GetJoyTouchpadFingers(int device, int touchpad = 0)
    {
        int[] ret = NativeCalls.godot_icall_2_780(MethodBind57, GodotObject.GetPtr(this), device, touchpad);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind58 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetJoyNumTouchpads, 923996154ul);

    /// <summary>
    /// <para>Returns the number of touchpads on the specified joypad, if it has any. Otherwise, the method returns <c>0</c>.</para>
    /// <para><b>Note:</b> This feature is only supported on Windows, Linux, macOS, and iOS.</para>
    /// </summary>
    public int GetJoyNumTouchpads(int device)
    {
        int ret = NativeCalls.godot_icall_1_85(MethodBind58, GodotObject.GetPtr(this), device);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind59 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetGravity, 3460891852ul);

    /// <summary>
    /// <para>Sets the gravity value of the accelerometer sensor. Can be used for debugging on devices without a hardware sensor, for example in an editor on a PC.</para>
    /// <para><b>Note:</b> This value can be immediately overwritten by the hardware sensor value on Android and iOS.</para>
    /// </summary>
    public unsafe void SetGravity(Vector3 value)
    {
        NativeCalls.godot_icall_1_203(MethodBind59, GodotObject.GetPtr(this), &value);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind60 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetAccelerometer, 3460891852ul);

    /// <summary>
    /// <para>Sets the acceleration value of the accelerometer sensor. Can be used for debugging on devices without a hardware sensor, for example in an editor on a PC.</para>
    /// <para><b>Note:</b> This value can be immediately overwritten by the hardware sensor value on Android and iOS.</para>
    /// </summary>
    public unsafe void SetAccelerometer(Vector3 value)
    {
        NativeCalls.godot_icall_1_203(MethodBind60, GodotObject.GetPtr(this), &value);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind61 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetMagnetometer, 3460891852ul);

    /// <summary>
    /// <para>Sets the value of the magnetic field of the magnetometer sensor. Can be used for debugging on devices without a hardware sensor, for example in an editor on a PC.</para>
    /// <para><b>Note:</b> This value can be immediately overwritten by the hardware sensor value on Android and iOS.</para>
    /// </summary>
    public unsafe void SetMagnetometer(Vector3 value)
    {
        NativeCalls.godot_icall_1_203(MethodBind61, GodotObject.GetPtr(this), &value);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind62 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetGyroscope, 3460891852ul);

    /// <summary>
    /// <para>Sets the value of the rotation rate of the gyroscope sensor. Can be used for debugging on devices without a hardware sensor, for example in an editor on a PC.</para>
    /// <para><b>Note:</b> This value can be immediately overwritten by the hardware sensor value on Android and iOS.</para>
    /// </summary>
    public unsafe void SetGyroscope(Vector3 value)
    {
        NativeCalls.godot_icall_1_203(MethodBind62, GodotObject.GetPtr(this), &value);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind63 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetDeviceOrientation, 1727505552ul);

    /// <summary>
    /// <para>Sets the device orientation quaternion. Can be used for debugging on devices without a hardware sensor, for example in an editor on a PC.</para>
    /// <para><b>Note:</b> This value can be immediately overwritten by the hardware sensor value on Android and iOS.</para>
    /// </summary>
    public unsafe void SetDeviceOrientation(Quaternion value)
    {
        NativeCalls.godot_icall_1_679(MethodBind63, GodotObject.GetPtr(this), &value);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind64 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetJoyLight, 2878471219ul);

    /// <summary>
    /// <para>Sets the joypad's LED light, if available, to the specified color. See also <see cref="Godot.InputInstance.HasJoyLight(int)"/>.</para>
    /// <para><b>Note:</b> There is no way to get the color of the light from a joypad. If you need to know the assigned color, store it separately.</para>
    /// <para><b>Note:</b> This feature is only supported on Windows, Linux, macOS, and iOS.</para>
    /// </summary>
    public unsafe void SetJoyLight(int device, Color color)
    {
        NativeCalls.godot_icall_2_717(MethodBind64, GodotObject.GetPtr(this), device, &color);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind65 = ClassDB_get_method_with_compatibility(NativeName, MethodName.HasJoyLight, 1116898809ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if the joypad has an LED light that can change colors and/or brightness. See also <see cref="Godot.InputInstance.SetJoyLight(int, Color)"/>.</para>
    /// <para><b>Note:</b> This feature is only supported on Windows, Linux, macOS, and iOS.</para>
    /// </summary>
    public bool HasJoyLight(int device)
    {
        bool ret = NativeCalls.godot_icall_1_86(MethodBind65, GodotObject.GetPtr(this), device).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind66 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetLastMouseVelocity, 1497962370ul);

    /// <summary>
    /// <para>Returns the last mouse velocity. To provide a precise and jitter-free velocity, mouse velocity is only calculated every 0.1s. Therefore, mouse velocity will lag mouse movements.</para>
    /// </summary>
    public Vector2 GetLastMouseVelocity()
    {
        Vector2 ret = NativeCalls.godot_icall_0_37(MethodBind66, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind67 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetLastMouseScreenVelocity, 1497962370ul);

    /// <summary>
    /// <para>Returns the last mouse velocity in screen coordinates. To provide a precise and jitter-free velocity, mouse velocity is only calculated every 0.1s. Therefore, mouse velocity will lag mouse movements.</para>
    /// </summary>
    public Vector2 GetLastMouseScreenVelocity()
    {
        Vector2 ret = NativeCalls.godot_icall_0_37(MethodBind67, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind68 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMouseButtonMask, 2512161324ul);

    /// <summary>
    /// <para>Returns mouse buttons as a bitmask. If multiple mouse buttons are pressed at the same time, the bits are added together. Equivalent to <see cref="Godot.DisplayServer.MouseGetButtonState()"/>.</para>
    /// </summary>
    public MouseButtonMask GetMouseButtonMask()
    {
        MouseButtonMask ret = (MouseButtonMask)NativeCalls.godot_icall_0_39(MethodBind68, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind69 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetMouseMode, 2228490894ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetMouseMode(Input.MouseModeEnum mode)
    {
        NativeCalls.godot_icall_1_38(MethodBind69, GodotObject.GetPtr(this), (int)mode);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind70 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMouseMode, 965286182ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Input.MouseModeEnum GetMouseMode()
    {
        Input.MouseModeEnum ret = (Input.MouseModeEnum)NativeCalls.godot_icall_0_39(MethodBind70, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind71 = ClassDB_get_method_with_compatibility(NativeName, MethodName.WarpMouse, 743155724ul);

    /// <summary>
    /// <para>Sets the mouse position to the specified vector, provided in pixels and relative to an origin at the upper left corner of the currently focused Window Manager game window.</para>
    /// <para>Mouse position is clipped to the limits of the screen resolution, or to the limits of the game window if <see cref="Godot.Input.MouseModeEnum"/> is set to <see cref="Godot.Input.MouseModeEnum.Confined"/> or <see cref="Godot.Input.MouseModeEnum.ConfinedHidden"/>.</para>
    /// <para><b>Note:</b> <see cref="Godot.InputInstance.WarpMouse(Vector2)"/> is only supported on Windows, macOS and Linux. It has no effect on Android, iOS and Web.</para>
    /// </summary>
    public unsafe void WarpMouse(Vector2 position)
    {
        NativeCalls.godot_icall_1_36(MethodBind71, GodotObject.GetPtr(this), &position);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind72 = ClassDB_get_method_with_compatibility(NativeName, MethodName.ActionPress, 1713091165ul);

    /// <summary>
    /// <para>Simulates pressing the specified input action.</para>
    /// <para>The <paramref name="strength"/> can be used for non-boolean actions, it's ranged between <c>0.0</c> and <c>1.0</c> representing the intensity of the given action.</para>
    /// <para><b>Note:</b> This method will not cause any <see cref="Godot.Node._Input(InputEvent)"/> calls. It is intended to be used with <see cref="Godot.InputInstance.IsActionPressed(StringName, bool)"/> and <see cref="Godot.InputInstance.IsActionJustPressed(StringName, bool)"/>. If you want to simulate <c>_input</c>, use <see cref="Godot.InputInstance.ParseInputEvent(InputEvent)"/> instead.</para>
    /// </summary>
    public void ActionPress(StringName action, float strength = 1.0f)
    {
        NativeCalls.godot_icall_2_789(MethodBind72, GodotObject.GetPtr(this), (godot_string_name)(action?.NativeValue ?? default), strength);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind73 = ClassDB_get_method_with_compatibility(NativeName, MethodName.ActionRelease, 3304788590ul);

    /// <summary>
    /// <para>Releases the specified input action, if the action is currently pressed.</para>
    /// </summary>
    public void ActionRelease(StringName action)
    {
        NativeCalls.godot_icall_1_88(MethodBind73, GodotObject.GetPtr(this), (godot_string_name)(action?.NativeValue ?? default));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind74 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetDefaultCursorShape, 2124816902ul);

    /// <summary>
    /// <para>Sets the default cursor shape to be used in the viewport instead of <see cref="Godot.Input.CursorShape.Arrow"/>.</para>
    /// <para><b>Note:</b> If you want to change the default cursor shape for <see cref="Godot.Control"/>'s nodes, use <see cref="Godot.Control.MouseDefaultCursorShape"/> instead.</para>
    /// <para><b>Note:</b> This method generates an <see cref="Godot.InputEventMouseMotion"/> to update cursor immediately.</para>
    /// </summary>
    public void SetDefaultCursorShape(Input.CursorShape shape = (Input.CursorShape)(0))
    {
        NativeCalls.godot_icall_1_38(MethodBind74, GodotObject.GetPtr(this), (int)shape);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind75 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetCurrentCursorShape, 3455658929ul);

    /// <summary>
    /// <para>Returns the currently assigned cursor shape.</para>
    /// </summary>
    public Input.CursorShape GetCurrentCursorShape()
    {
        Input.CursorShape ret = (Input.CursorShape)NativeCalls.godot_icall_0_39(MethodBind75, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind76 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetCustomMouseCursor, 703945977ul);

    /// <summary>
    /// <para>Sets a custom mouse cursor image, which is only visible inside the game window, for the given mouse <paramref name="shape"/>. The hotspot can also be specified. Passing <see langword="null"/> to the image parameter resets to the system cursor.</para>
    /// <para><paramref name="image"/> can be either <see cref="Godot.Texture2D"/> or <see cref="Godot.Image"/> and its size must be lower than or equal to 256×256. To avoid rendering issues, sizes lower than or equal to 128×128 are recommended.</para>
    /// <para><paramref name="hotspot"/> must be within <paramref name="image"/>'s size.</para>
    /// <para><b>Note:</b> <see cref="Godot.AnimatedTexture"/>s aren't supported as custom mouse cursors. If using an <see cref="Godot.AnimatedTexture"/>, only the first frame will be displayed.</para>
    /// <para><b>Note:</b> The <b>Lossless</b>, <b>Lossy</b> or <b>Uncompressed</b> compression modes are recommended. The <b>Video RAM</b> compression mode can be used, but it will be decompressed on the CPU, which means loading times are slowed down and no memory is saved compared to lossless modes.</para>
    /// <para><b>Note:</b> On the web platform, the maximum allowed cursor image size is 128×128. Cursor images larger than 32×32 will also only be displayed if the mouse cursor image is entirely located within the page for <a href="https://chromestatus.com/feature/5825971391299584">security reasons</a>.</para>
    /// </summary>
    /// <param name="hotspot">If the parameter is null, then the default value is <c>new Vector2(0.0f, 0.0f)</c>.</param>
    public unsafe void SetCustomMouseCursor(Resource image, Input.CursorShape shape = (Input.CursorShape)(0), Nullable<Vector2> hotspot = null)
    {
        Vector2 hotspotOrDefVal = hotspot.HasValue ? hotspot.Value : new Vector2(0.0f, 0.0f);
        NativeCalls.godot_icall_3_452(MethodBind76, GodotObject.GetPtr(this), GodotObject.GetPtr(image), (int)shape, &hotspotOrDefVal);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind77 = ClassDB_get_method_with_compatibility(NativeName, MethodName.ParseInputEvent, 3754044979ul);

    /// <summary>
    /// <para>Feeds an <see cref="Godot.InputEvent"/> to the game. Can be used to artificially trigger input events from code. Also generates <see cref="Godot.Node._Input(InputEvent)"/> calls.</para>
    /// <para><code>
    /// var cancelEvent = new InputEventAction();
    /// cancelEvent.Action = "ui_cancel";
    /// cancelEvent.Pressed = true;
    /// Input.ParseInputEvent(cancelEvent);
    /// </code></para>
    /// <para><b>Note:</b> Calling this function has no influence on the operating system. So for example sending an <see cref="Godot.InputEventMouseMotion"/> will not move the OS mouse cursor to the specified position (use <see cref="Godot.InputInstance.WarpMouse(Vector2)"/> instead) and sending Alt/Cmd + Tab as <see cref="Godot.InputEventKey"/> won't toggle between active windows.</para>
    /// </summary>
    public void ParseInputEvent(InputEvent @event)
    {
        NativeCalls.godot_icall_1_56(MethodBind77, GodotObject.GetPtr(this), GodotObject.GetPtr(@event));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind78 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetUseAccumulatedInput, 2586408642ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetUseAccumulatedInput(bool enable)
    {
        NativeCalls.godot_icall_1_14(MethodBind78, GodotObject.GetPtr(this), enable.ToGodotBool());
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind79 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsUsingAccumulatedInput, 2240911060ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public bool IsUsingAccumulatedInput()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind79, GodotObject.GetPtr(this)).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind80 = ClassDB_get_method_with_compatibility(NativeName, MethodName.FlushBufferedEvents, 3218959716ul);

    /// <summary>
    /// <para>Sends all buffered input events to the game loop. These events may have been buffered as a result of accumulated input (<see cref="Godot.InputInstance.UseAccumulatedInput"/>) or agile input flushing (<c>ProjectSettings.input_devices/buffering/agile_event_flushing</c>).</para>
    /// <para>The engine will already do this itself at key execution points (at least once per frame). However, this can be useful in advanced cases where you want precise control over the timing of event handling.</para>
    /// </summary>
    public void FlushBufferedEvents()
    {
        NativeCalls.godot_icall_0_3(MethodBind80, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind81 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetEmulateMouseFromTouch, 2586408642ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetEmulateMouseFromTouch(bool enable)
    {
        NativeCalls.godot_icall_1_14(MethodBind81, GodotObject.GetPtr(this), enable.ToGodotBool());
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind82 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsEmulatingMouseFromTouch, 36873697ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public bool IsEmulatingMouseFromTouch()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind82, GodotObject.GetPtr(this)).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind83 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetEmulateTouchFromMouse, 2586408642ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetEmulateTouchFromMouse(bool enable)
    {
        NativeCalls.godot_icall_1_14(MethodBind83, GodotObject.GetPtr(this), enable.ToGodotBool());
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind84 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsEmulatingTouchFromMouse, 36873697ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public bool IsEmulatingTouchFromMouse()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind84, GodotObject.GetPtr(this)).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind85 = ClassDB_get_method_with_compatibility(NativeName, MethodName.VibrateHandheld, 955504365ul);

    /// <summary>
    /// <para>Starts vibrating the handheld device for the specified duration in milliseconds.</para>
    /// <para><paramref name="amplitude"/> is the strength of the vibration, as a value between <c>0.0</c> and <c>1.0</c>. If set to <c>-1.0</c>, the default vibration strength of the device is used.</para>
    /// <para><b>Note:</b> This method is implemented on Android, iOS, and Web. It has no effect on other platforms.</para>
    /// <para><b>Note:</b> For Android, <see cref="Godot.InputInstance.VibrateHandheld(int, float)"/> requires enabling the <c>VIBRATE</c> permission in the export preset. Otherwise, <see cref="Godot.InputInstance.VibrateHandheld(int, float)"/> will have no effect.</para>
    /// <para><b>Note:</b> For iOS, specifying the duration is only supported in iOS 13 and later.</para>
    /// <para><b>Note:</b> For Web, the amplitude cannot be changed.</para>
    /// <para><b>Note:</b> Some web browsers such as Safari and Firefox for Android do not support <see cref="Godot.InputInstance.VibrateHandheld(int, float)"/>.</para>
    /// <para><b>Note:</b> Device settings such as vibration on/off, "do not disturb" mode or specific haptic feedback on/off may prevent <see cref="Godot.InputInstance.VibrateHandheld(int, float)"/> effects.</para>
    /// </summary>
    [EditorBrowsable(EditorBrowsableState.Never)]
    public void VibrateHandheld(int durationMs)
    {
        NativeCalls.godot_icall_1_38(MethodBind85, GodotObject.GetPtr(this), durationMs);
        global::System.GC.KeepAlive(this);
    }

    /// <summary>
    /// Represents the method that handles the <see cref="Godot.InputInstance.JoyConnectionChanged"/> event of a <see cref="Godot.InputInstance"/> class.
    /// </summary>
    public delegate void JoyConnectionChangedEventHandler(long device, bool connected);

    private static void JoyConnectionChangedTrampoline(object delegateObj, NativeVariantPtrArgs args, out godot_variant ret)
    {
        Callable.ThrowIfArgCountMismatch(args, 2);
        ((JoyConnectionChangedEventHandler)delegateObj)(VariantUtils.ConvertTo<long>(args[0]), VariantUtils.ConvertTo<bool>(args[1]));
        ret = default;
    }

    /// <summary>
    /// <para>Emitted when a joypad device has been connected or disconnected.</para>
    /// </summary>
    public unsafe event JoyConnectionChangedEventHandler JoyConnectionChanged
    {
        add => Connect(SignalName.JoyConnectionChanged, Callable.CreateWithUnsafeTrampoline(value, &JoyConnectionChangedTrampoline));
        remove => Disconnect(SignalName.JoyConnectionChanged, Callable.CreateWithUnsafeTrampoline(value, &JoyConnectionChangedTrampoline));
    }

    protected void EmitSignalJoyConnectionChanged(long device, bool connected)
    {
        EmitSignal(SignalName.JoyConnectionChanged, device, connected);
    }

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_joy_connection_changed = "JoyConnectionChanged";

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
        if (signal == SignalName.JoyConnectionChanged)
        {
            if (HasGodotClassSignal(SignalProxyName_joy_connection_changed.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        return base.HasGodotClassSignal(signal);
    }

    /// <summary>
    /// Cached StringNames for the properties and fields contained in this class, for fast lookup.
    /// </summary>
    public new class PropertyName : GodotObject.PropertyName
    {
        /// <summary>
        /// Cached name for the 'mouse_mode' property.
        /// </summary>
        public static readonly StringName MouseMode = "mouse_mode";
        /// <summary>
        /// Cached name for the 'use_accumulated_input' property.
        /// </summary>
        public static readonly StringName UseAccumulatedInput = "use_accumulated_input";
        /// <summary>
        /// Cached name for the 'emulate_mouse_from_touch' property.
        /// </summary>
        public static readonly StringName EmulateMouseFromTouch = "emulate_mouse_from_touch";
        /// <summary>
        /// Cached name for the 'emulate_touch_from_mouse' property.
        /// </summary>
        public static readonly StringName EmulateTouchFromMouse = "emulate_touch_from_mouse";
        /// <summary>
        /// Cached name for the 'ignore_joypad_on_unfocused_application' property.
        /// </summary>
        public static readonly StringName IgnoreJoypadOnUnfocusedApplication = "ignore_joypad_on_unfocused_application";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : GodotObject.MethodName
    {
        /// <summary>
        /// Cached name for the 'is_anything_pressed' method.
        /// </summary>
        public static readonly StringName IsAnythingPressed = "is_anything_pressed";
        /// <summary>
        /// Cached name for the 'is_key_pressed' method.
        /// </summary>
        public static readonly StringName IsKeyPressed = "is_key_pressed";
        /// <summary>
        /// Cached name for the 'is_physical_key_pressed' method.
        /// </summary>
        public static readonly StringName IsPhysicalKeyPressed = "is_physical_key_pressed";
        /// <summary>
        /// Cached name for the 'is_key_label_pressed' method.
        /// </summary>
        public static readonly StringName IsKeyLabelPressed = "is_key_label_pressed";
        /// <summary>
        /// Cached name for the 'is_mouse_button_pressed' method.
        /// </summary>
        public static readonly StringName IsMouseButtonPressed = "is_mouse_button_pressed";
        /// <summary>
        /// Cached name for the 'is_joy_button_pressed' method.
        /// </summary>
        public static readonly StringName IsJoyButtonPressed = "is_joy_button_pressed";
        /// <summary>
        /// Cached name for the 'is_action_pressed' method.
        /// </summary>
        public static readonly StringName IsActionPressed = "is_action_pressed";
        /// <summary>
        /// Cached name for the 'is_action_just_pressed' method.
        /// </summary>
        public static readonly StringName IsActionJustPressed = "is_action_just_pressed";
        /// <summary>
        /// Cached name for the 'is_action_just_released' method.
        /// </summary>
        public static readonly StringName IsActionJustReleased = "is_action_just_released";
        /// <summary>
        /// Cached name for the 'is_action_just_pressed_by_event' method.
        /// </summary>
        public static readonly StringName IsActionJustPressedByEvent = "is_action_just_pressed_by_event";
        /// <summary>
        /// Cached name for the 'is_action_just_released_by_event' method.
        /// </summary>
        public static readonly StringName IsActionJustReleasedByEvent = "is_action_just_released_by_event";
        /// <summary>
        /// Cached name for the 'get_action_strength' method.
        /// </summary>
        public static readonly StringName GetActionStrength = "get_action_strength";
        /// <summary>
        /// Cached name for the 'get_action_raw_strength' method.
        /// </summary>
        public static readonly StringName GetActionRawStrength = "get_action_raw_strength";
        /// <summary>
        /// Cached name for the 'get_axis' method.
        /// </summary>
        public static readonly StringName GetAxis = "get_axis";
        /// <summary>
        /// Cached name for the 'get_vector' method.
        /// </summary>
        public static readonly StringName GetVector = "get_vector";
        /// <summary>
        /// Cached name for the 'add_joy_mapping' method.
        /// </summary>
        public static readonly StringName AddJoyMapping = "add_joy_mapping";
        /// <summary>
        /// Cached name for the 'remove_joy_mapping' method.
        /// </summary>
        public static readonly StringName RemoveJoyMapping = "remove_joy_mapping";
        /// <summary>
        /// Cached name for the 'is_joy_known' method.
        /// </summary>
        public static readonly StringName IsJoyKnown = "is_joy_known";
        /// <summary>
        /// Cached name for the 'get_joy_axis' method.
        /// </summary>
        public static readonly StringName GetJoyAxis = "get_joy_axis";
        /// <summary>
        /// Cached name for the 'get_joy_name' method.
        /// </summary>
        public static readonly StringName GetJoyName = "get_joy_name";
        /// <summary>
        /// Cached name for the 'get_joy_guid' method.
        /// </summary>
        public static readonly StringName GetJoyGuid = "get_joy_guid";
        /// <summary>
        /// Cached name for the 'get_joy_info' method.
        /// </summary>
        public static readonly StringName GetJoyInfo = "get_joy_info";
        /// <summary>
        /// Cached name for the 'should_ignore_device' method.
        /// </summary>
        public static readonly StringName ShouldIgnoreDevice = "should_ignore_device";
        /// <summary>
        /// Cached name for the 'get_connected_joypads' method.
        /// </summary>
        public static readonly StringName GetConnectedJoypads = "get_connected_joypads";
        /// <summary>
        /// Cached name for the 'get_joy_vibration_strength' method.
        /// </summary>
        public static readonly StringName GetJoyVibrationStrength = "get_joy_vibration_strength";
        /// <summary>
        /// Cached name for the 'get_joy_vibration_duration' method.
        /// </summary>
        public static readonly StringName GetJoyVibrationDuration = "get_joy_vibration_duration";
        /// <summary>
        /// Cached name for the 'get_joy_vibration_remaining_duration' method.
        /// </summary>
        public static readonly StringName GetJoyVibrationRemainingDuration = "get_joy_vibration_remaining_duration";
        /// <summary>
        /// Cached name for the 'is_joy_vibrating' method.
        /// </summary>
        public static readonly StringName IsJoyVibrating = "is_joy_vibrating";
        /// <summary>
        /// Cached name for the 'has_joy_vibration' method.
        /// </summary>
        public static readonly StringName HasJoyVibration = "has_joy_vibration";
        /// <summary>
        /// Cached name for the 'start_joy_vibration' method.
        /// </summary>
        public static readonly StringName StartJoyVibration = "start_joy_vibration";
        /// <summary>
        /// Cached name for the 'stop_joy_vibration' method.
        /// </summary>
        public static readonly StringName StopJoyVibration = "stop_joy_vibration";
        /// <summary>
        /// Cached name for the 'vibrate_handheld' method.
        /// </summary>
        public static readonly StringName VibrateHandheld = "vibrate_handheld";
        /// <summary>
        /// Cached name for the 'set_ignore_joypad_on_unfocused_application' method.
        /// </summary>
        public static readonly StringName SetIgnoreJoypadOnUnfocusedApplication = "set_ignore_joypad_on_unfocused_application";
        /// <summary>
        /// Cached name for the 'is_ignoring_joypad_on_unfocused_application' method.
        /// </summary>
        public static readonly StringName IsIgnoringJoypadOnUnfocusedApplication = "is_ignoring_joypad_on_unfocused_application";
        /// <summary>
        /// Cached name for the 'get_gravity' method.
        /// </summary>
        public static readonly StringName GetGravity = "get_gravity";
        /// <summary>
        /// Cached name for the 'get_accelerometer' method.
        /// </summary>
        public static readonly StringName GetAccelerometer = "get_accelerometer";
        /// <summary>
        /// Cached name for the 'get_magnetometer' method.
        /// </summary>
        public static readonly StringName GetMagnetometer = "get_magnetometer";
        /// <summary>
        /// Cached name for the 'get_gyroscope' method.
        /// </summary>
        public static readonly StringName GetGyroscope = "get_gyroscope";
        /// <summary>
        /// Cached name for the 'get_device_orientation' method.
        /// </summary>
        public static readonly StringName GetDeviceOrientation = "get_device_orientation";
        /// <summary>
        /// Cached name for the 'get_joy_accelerometer' method.
        /// </summary>
        public static readonly StringName GetJoyAccelerometer = "get_joy_accelerometer";
        /// <summary>
        /// Cached name for the 'get_joy_gravity' method.
        /// </summary>
        public static readonly StringName GetJoyGravity = "get_joy_gravity";
        /// <summary>
        /// Cached name for the 'get_joy_gyroscope' method.
        /// </summary>
        public static readonly StringName GetJoyGyroscope = "get_joy_gyroscope";
        /// <summary>
        /// Cached name for the 'get_joy_motion_sensors_rate' method.
        /// </summary>
        public static readonly StringName GetJoyMotionSensorsRate = "get_joy_motion_sensors_rate";
        /// <summary>
        /// Cached name for the 'is_joy_motion_sensors_enabled' method.
        /// </summary>
        public static readonly StringName IsJoyMotionSensorsEnabled = "is_joy_motion_sensors_enabled";
        /// <summary>
        /// Cached name for the 'set_joy_motion_sensors_enabled' method.
        /// </summary>
        public static readonly StringName SetJoyMotionSensorsEnabled = "set_joy_motion_sensors_enabled";
        /// <summary>
        /// Cached name for the 'has_joy_motion_sensors' method.
        /// </summary>
        public static readonly StringName HasJoyMotionSensors = "has_joy_motion_sensors";
        /// <summary>
        /// Cached name for the 'start_joy_motion_sensors_calibration' method.
        /// </summary>
        public static readonly StringName StartJoyMotionSensorsCalibration = "start_joy_motion_sensors_calibration";
        /// <summary>
        /// Cached name for the 'stop_joy_motion_sensors_calibration' method.
        /// </summary>
        public static readonly StringName StopJoyMotionSensorsCalibration = "stop_joy_motion_sensors_calibration";
        /// <summary>
        /// Cached name for the 'clear_joy_motion_sensors_calibration' method.
        /// </summary>
        public static readonly StringName ClearJoyMotionSensorsCalibration = "clear_joy_motion_sensors_calibration";
        /// <summary>
        /// Cached name for the 'get_joy_motion_sensors_calibration' method.
        /// </summary>
        public static readonly StringName GetJoyMotionSensorsCalibration = "get_joy_motion_sensors_calibration";
        /// <summary>
        /// Cached name for the 'set_joy_motion_sensors_calibration' method.
        /// </summary>
        public static readonly StringName SetJoyMotionSensorsCalibration = "set_joy_motion_sensors_calibration";
        /// <summary>
        /// Cached name for the 'is_joy_motion_sensors_calibrated' method.
        /// </summary>
        public static readonly StringName IsJoyMotionSensorsCalibrated = "is_joy_motion_sensors_calibrated";
        /// <summary>
        /// Cached name for the 'is_joy_motion_sensors_calibrating' method.
        /// </summary>
        public static readonly StringName IsJoyMotionSensorsCalibrating = "is_joy_motion_sensors_calibrating";
        /// <summary>
        /// Cached name for the 'set_joy_motion_sensors_auto_calibration_enabled' method.
        /// </summary>
        public static readonly StringName SetJoyMotionSensorsAutoCalibrationEnabled = "set_joy_motion_sensors_auto_calibration_enabled";
        /// <summary>
        /// Cached name for the 'is_joy_motion_sensors_auto_calibration_enabled' method.
        /// </summary>
        public static readonly StringName IsJoyMotionSensorsAutoCalibrationEnabled = "is_joy_motion_sensors_auto_calibration_enabled";
        /// <summary>
        /// Cached name for the 'get_joy_touchpad_finger_position' method.
        /// </summary>
        public static readonly StringName GetJoyTouchpadFingerPosition = "get_joy_touchpad_finger_position";
        /// <summary>
        /// Cached name for the 'get_joy_touchpad_finger_pressure' method.
        /// </summary>
        public static readonly StringName GetJoyTouchpadFingerPressure = "get_joy_touchpad_finger_pressure";
        /// <summary>
        /// Cached name for the 'get_joy_touchpad_fingers' method.
        /// </summary>
        public static readonly StringName GetJoyTouchpadFingers = "get_joy_touchpad_fingers";
        /// <summary>
        /// Cached name for the 'get_joy_num_touchpads' method.
        /// </summary>
        public static readonly StringName GetJoyNumTouchpads = "get_joy_num_touchpads";
        /// <summary>
        /// Cached name for the 'set_gravity' method.
        /// </summary>
        public static readonly StringName SetGravity = "set_gravity";
        /// <summary>
        /// Cached name for the 'set_accelerometer' method.
        /// </summary>
        public static readonly StringName SetAccelerometer = "set_accelerometer";
        /// <summary>
        /// Cached name for the 'set_magnetometer' method.
        /// </summary>
        public static readonly StringName SetMagnetometer = "set_magnetometer";
        /// <summary>
        /// Cached name for the 'set_gyroscope' method.
        /// </summary>
        public static readonly StringName SetGyroscope = "set_gyroscope";
        /// <summary>
        /// Cached name for the 'set_device_orientation' method.
        /// </summary>
        public static readonly StringName SetDeviceOrientation = "set_device_orientation";
        /// <summary>
        /// Cached name for the 'set_joy_light' method.
        /// </summary>
        public static readonly StringName SetJoyLight = "set_joy_light";
        /// <summary>
        /// Cached name for the 'has_joy_light' method.
        /// </summary>
        public static readonly StringName HasJoyLight = "has_joy_light";
        /// <summary>
        /// Cached name for the 'get_last_mouse_velocity' method.
        /// </summary>
        public static readonly StringName GetLastMouseVelocity = "get_last_mouse_velocity";
        /// <summary>
        /// Cached name for the 'get_last_mouse_screen_velocity' method.
        /// </summary>
        public static readonly StringName GetLastMouseScreenVelocity = "get_last_mouse_screen_velocity";
        /// <summary>
        /// Cached name for the 'get_mouse_button_mask' method.
        /// </summary>
        public static readonly StringName GetMouseButtonMask = "get_mouse_button_mask";
        /// <summary>
        /// Cached name for the 'set_mouse_mode' method.
        /// </summary>
        public static readonly StringName SetMouseMode = "set_mouse_mode";
        /// <summary>
        /// Cached name for the 'get_mouse_mode' method.
        /// </summary>
        public static readonly StringName GetMouseMode = "get_mouse_mode";
        /// <summary>
        /// Cached name for the 'warp_mouse' method.
        /// </summary>
        public static readonly StringName WarpMouse = "warp_mouse";
        /// <summary>
        /// Cached name for the 'action_press' method.
        /// </summary>
        public static readonly StringName ActionPress = "action_press";
        /// <summary>
        /// Cached name for the 'action_release' method.
        /// </summary>
        public static readonly StringName ActionRelease = "action_release";
        /// <summary>
        /// Cached name for the 'set_default_cursor_shape' method.
        /// </summary>
        public static readonly StringName SetDefaultCursorShape = "set_default_cursor_shape";
        /// <summary>
        /// Cached name for the 'get_current_cursor_shape' method.
        /// </summary>
        public static readonly StringName GetCurrentCursorShape = "get_current_cursor_shape";
        /// <summary>
        /// Cached name for the 'set_custom_mouse_cursor' method.
        /// </summary>
        public static readonly StringName SetCustomMouseCursor = "set_custom_mouse_cursor";
        /// <summary>
        /// Cached name for the 'parse_input_event' method.
        /// </summary>
        public static readonly StringName ParseInputEvent = "parse_input_event";
        /// <summary>
        /// Cached name for the 'set_use_accumulated_input' method.
        /// </summary>
        public static readonly StringName SetUseAccumulatedInput = "set_use_accumulated_input";
        /// <summary>
        /// Cached name for the 'is_using_accumulated_input' method.
        /// </summary>
        public static readonly StringName IsUsingAccumulatedInput = "is_using_accumulated_input";
        /// <summary>
        /// Cached name for the 'flush_buffered_events' method.
        /// </summary>
        public static readonly StringName FlushBufferedEvents = "flush_buffered_events";
        /// <summary>
        /// Cached name for the 'set_emulate_mouse_from_touch' method.
        /// </summary>
        public static readonly StringName SetEmulateMouseFromTouch = "set_emulate_mouse_from_touch";
        /// <summary>
        /// Cached name for the 'is_emulating_mouse_from_touch' method.
        /// </summary>
        public static readonly StringName IsEmulatingMouseFromTouch = "is_emulating_mouse_from_touch";
        /// <summary>
        /// Cached name for the 'set_emulate_touch_from_mouse' method.
        /// </summary>
        public static readonly StringName SetEmulateTouchFromMouse = "set_emulate_touch_from_mouse";
        /// <summary>
        /// Cached name for the 'is_emulating_touch_from_mouse' method.
        /// </summary>
        public static readonly StringName IsEmulatingTouchFromMouse = "is_emulating_touch_from_mouse";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : GodotObject.SignalName
    {
        /// <summary>
        /// Cached name for the 'joy_connection_changed' signal.
        /// </summary>
        public static readonly StringName JoyConnectionChanged = "joy_connection_changed";
    }
}
