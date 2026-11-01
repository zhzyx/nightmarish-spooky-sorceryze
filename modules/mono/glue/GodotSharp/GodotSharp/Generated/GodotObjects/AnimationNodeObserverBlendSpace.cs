namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
public partial class AnimationNodeObserverBlendSpace : AnimationNodeObserver
{
    private static readonly System.Type CachedType = typeof(AnimationNodeObserverBlendSpace);

    private static readonly StringName NativeName = "AnimationNodeObserverBlendSpace";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public AnimationNodeObserverBlendSpace() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal AnimationNodeObserverBlendSpace(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal AnimationNodeObserverBlendSpace(bool memoryOwn) : base(memoryOwn) { }

    /// <summary>
    /// Represents the method that handles the <see cref="Godot.AnimationNodeObserverBlendSpace.ClosestPointChanged"/> event of a <see cref="Godot.AnimationNodeObserverBlendSpace"/> class.
    /// </summary>
    public delegate void ClosestPointChangedEventHandler(StringName closestPointName);

    private static void ClosestPointChangedTrampoline(object delegateObj, NativeVariantPtrArgs args, out godot_variant ret)
    {
        Callable.ThrowIfArgCountMismatch(args, 1);
        ((ClosestPointChangedEventHandler)delegateObj)(VariantUtils.ConvertTo<StringName>(args[0]));
        ret = default;
    }

    /// <summary>
    /// <para>Emitted when the closest point to the current blend position changes.</para>
    /// </summary>
    public unsafe event ClosestPointChangedEventHandler ClosestPointChanged
    {
        add => Connect(SignalName.ClosestPointChanged, Callable.CreateWithUnsafeTrampoline(value, &ClosestPointChangedTrampoline));
        remove => Disconnect(SignalName.ClosestPointChanged, Callable.CreateWithUnsafeTrampoline(value, &ClosestPointChangedTrampoline));
    }

    protected void EmitSignalClosestPointChanged(StringName closestPointName)
    {
        EmitSignal(SignalName.ClosestPointChanged, closestPointName);
    }

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_closest_point_changed = "ClosestPointChanged";

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
        if (signal == SignalName.ClosestPointChanged)
        {
            if (HasGodotClassSignal(SignalProxyName_closest_point_changed.NativeValue.DangerousSelfRef))
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
        /// Cached name for the 'closest_point_changed' signal.
        /// </summary>
        public static readonly StringName ClosestPointChanged = "closest_point_changed";
    }
}
