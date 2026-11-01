namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
public partial class AnimationNodeObserverOneShot : AnimationNodeObserver
{
    private static readonly System.Type CachedType = typeof(AnimationNodeObserverOneShot);

    private static readonly StringName NativeName = "AnimationNodeObserverOneShot";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public AnimationNodeObserverOneShot() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal AnimationNodeObserverOneShot(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal AnimationNodeObserverOneShot(bool memoryOwn) : base(memoryOwn) { }

    /// <summary>
    /// <para>Emitted when the one-shot has started.</para>
    /// </summary>
    public event Action Started
    {
        add => Connect(SignalName.Started, Callable.From(value));
        remove => Disconnect(SignalName.Started, Callable.From(value));
    }

    protected void EmitSignalStarted()
    {
        EmitSignal(SignalName.Started);
    }

    /// <summary>
    /// <para>Emitted when the one-shot has finished fading in. Only emitted if fade-in time is greater than zero.</para>
    /// </summary>
    public event Action FadeInFinished
    {
        add => Connect(SignalName.FadeInFinished, Callable.From(value));
        remove => Disconnect(SignalName.FadeInFinished, Callable.From(value));
    }

    protected void EmitSignalFadeInFinished()
    {
        EmitSignal(SignalName.FadeInFinished);
    }

    /// <summary>
    /// <para>Emitted when the one-shot has started fading out. Only emitted if fade-out time is greater than zero.</para>
    /// </summary>
    public event Action FadeOutStarted
    {
        add => Connect(SignalName.FadeOutStarted, Callable.From(value));
        remove => Disconnect(SignalName.FadeOutStarted, Callable.From(value));
    }

    protected void EmitSignalFadeOutStarted()
    {
        EmitSignal(SignalName.FadeOutStarted);
    }

    /// <summary>
    /// <para>Emitted when the one-shot has finished.</para>
    /// </summary>
    public event Action Finished
    {
        add => Connect(SignalName.Finished, Callable.From(value));
        remove => Disconnect(SignalName.Finished, Callable.From(value));
    }

    protected void EmitSignalFinished()
    {
        EmitSignal(SignalName.Finished);
    }

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_started = "Started";

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_fade_in_finished = "FadeInFinished";

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_fade_out_started = "FadeOutStarted";

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_finished = "Finished";

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
        if (signal == SignalName.Started)
        {
            if (HasGodotClassSignal(SignalProxyName_started.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        if (signal == SignalName.FadeInFinished)
        {
            if (HasGodotClassSignal(SignalProxyName_fade_in_finished.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        if (signal == SignalName.FadeOutStarted)
        {
            if (HasGodotClassSignal(SignalProxyName_fade_out_started.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        if (signal == SignalName.Finished)
        {
            if (HasGodotClassSignal(SignalProxyName_finished.NativeValue.DangerousSelfRef))
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
        /// Cached name for the 'started' signal.
        /// </summary>
        public static readonly StringName Started = "started";
        /// <summary>
        /// Cached name for the 'fade_in_finished' signal.
        /// </summary>
        public static readonly StringName FadeInFinished = "fade_in_finished";
        /// <summary>
        /// Cached name for the 'fade_out_started' signal.
        /// </summary>
        public static readonly StringName FadeOutStarted = "fade_out_started";
        /// <summary>
        /// Cached name for the 'finished' signal.
        /// </summary>
        public static readonly StringName Finished = "finished";
    }
}
