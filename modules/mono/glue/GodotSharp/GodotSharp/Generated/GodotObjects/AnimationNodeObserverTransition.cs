namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
public partial class AnimationNodeObserverTransition : AnimationNodeObserver
{
    private static readonly System.Type CachedType = typeof(AnimationNodeObserverTransition);

    private static readonly StringName NativeName = "AnimationNodeObserverTransition";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public AnimationNodeObserverTransition() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal AnimationNodeObserverTransition(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal AnimationNodeObserverTransition(bool memoryOwn) : base(memoryOwn) { }

    /// <summary>
    /// Represents the method that handles the <see cref="Godot.AnimationNodeObserverTransition.StateStarted"/> event of a <see cref="Godot.AnimationNodeObserverTransition"/> class.
    /// </summary>
    public delegate void StateStartedEventHandler(string state);

    private static void StateStartedTrampoline(object delegateObj, NativeVariantPtrArgs args, out godot_variant ret)
    {
        Callable.ThrowIfArgCountMismatch(args, 1);
        ((StateStartedEventHandler)delegateObj)(VariantUtils.ConvertTo<string>(args[0]));
        ret = default;
    }

    /// <summary>
    /// <para>Emitted when a transition to a new state starts.</para>
    /// </summary>
    public unsafe event StateStartedEventHandler StateStarted
    {
        add => Connect(SignalName.StateStarted, Callable.CreateWithUnsafeTrampoline(value, &StateStartedTrampoline));
        remove => Disconnect(SignalName.StateStarted, Callable.CreateWithUnsafeTrampoline(value, &StateStartedTrampoline));
    }

    protected void EmitSignalStateStarted(string state)
    {
        EmitSignal(SignalName.StateStarted, state);
    }

    /// <summary>
    /// Represents the method that handles the <see cref="Godot.AnimationNodeObserverTransition.StateFinished"/> event of a <see cref="Godot.AnimationNodeObserverTransition"/> class.
    /// </summary>
    public delegate void StateFinishedEventHandler(string state);

    private static void StateFinishedTrampoline(object delegateObj, NativeVariantPtrArgs args, out godot_variant ret)
    {
        Callable.ThrowIfArgCountMismatch(args, 1);
        ((StateFinishedEventHandler)delegateObj)(VariantUtils.ConvertTo<string>(args[0]));
        ret = default;
    }

    /// <summary>
    /// <para>Emitted when transitioning out of a state. If crossfade time is greater than zero, emits when the crossfade finishes. Otherwise, emits immediately before <see cref="Godot.AnimationNodeObserverTransition.StateStarted"/> emits for the new state.</para>
    /// </summary>
    public unsafe event StateFinishedEventHandler StateFinished
    {
        add => Connect(SignalName.StateFinished, Callable.CreateWithUnsafeTrampoline(value, &StateFinishedTrampoline));
        remove => Disconnect(SignalName.StateFinished, Callable.CreateWithUnsafeTrampoline(value, &StateFinishedTrampoline));
    }

    protected void EmitSignalStateFinished(string state)
    {
        EmitSignal(SignalName.StateFinished, state);
    }

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_state_started = "StateStarted";

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_state_finished = "StateFinished";

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
        if (signal == SignalName.StateStarted)
        {
            if (HasGodotClassSignal(SignalProxyName_state_started.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        if (signal == SignalName.StateFinished)
        {
            if (HasGodotClassSignal(SignalProxyName_state_finished.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        return base.HasGodotClassSignal(signal);
    }

    /// <summary>
    /// Cached StringNames for the properties and fields contained in this class, for fast lookup.
    /// </summary>
    public new class PropertyName : AnimationNodeObserver.PropertyName
    {
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : AnimationNodeObserver.MethodName
    {
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : AnimationNodeObserver.SignalName
    {
        /// <summary>
        /// Cached name for the 'state_started' signal.
        /// </summary>
        public static readonly StringName StateStarted = "state_started";
        /// <summary>
        /// Cached name for the 'state_finished' signal.
        /// </summary>
        public static readonly StringName StateFinished = "state_finished";
    }
}
