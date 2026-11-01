namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>A resource used by <see cref="Godot.AnimationNodeBlendTree"/>.</para>
/// <para><see cref="Godot.AnimationNodeBlendSpace1D"/> represents a virtual axis on which any type of <see cref="Godot.AnimationRootNode"/>s can be added using <see cref="Godot.AnimationNodeBlendSpace1D.AddBlendPoint(AnimationRootNode, float, int, StringName)"/>. Outputs the linear blend of the two <see cref="Godot.AnimationRootNode"/>s adjacent to the current value.</para>
/// <para>You can set the extents of the axis with <see cref="Godot.AnimationNodeBlendSpace1D.MinSpace"/> and <see cref="Godot.AnimationNodeBlendSpace1D.MaxSpace"/>.</para>
/// <para></para>
/// <para>Optionally, signals can be used by setting an <see cref="Godot.AnimationNodeObserverBlendSpace"/> through <see cref="Godot.AnimationTree"/>.</para>
/// <para><code>
/// var observer = animationTree.Get("parameters/BlendSpace/observer").As&lt;AnimationNodeObserverBlendSpace&gt;();
/// observer.ClosestPointChanged += OnClosestPointChanged;
/// </code></para>
/// </summary>
public partial class AnimationNodeBlendSpace1D : AnimationRootNode
{
    public enum BlendModeEnum : long
    {
        /// <summary>
        /// <para>The interpolation between animations is linear.</para>
        /// </summary>
        Interpolated = 0,
        /// <summary>
        /// <para>The blend space plays the animation of the animation node which blending position is closest to. Useful for frame-by-frame 2D animations.</para>
        /// </summary>
        Discrete = 1,
        /// <summary>
        /// <para>Similar to <see cref="Godot.AnimationNodeBlendSpace1D.BlendModeEnum.Discrete"/>, but starts the new animation at the last animation's playback position.</para>
        /// </summary>
        DiscreteCarry = 2
    }

    public enum SyncModeEnum : long
    {
        /// <summary>
        /// <para>Inactive animations are frozen and do not advance.</para>
        /// </summary>
        None = 0,
        /// <summary>
        /// <para>Inactive animations advance with a weight of <c>0</c>. This is equivalent to the previous <c>sync = true</c> behavior.</para>
        /// </summary>
        Independent = 1,
        /// <summary>
        /// <para>All animations are time-scaled so they stay in sync, with the cycle length dynamically computed from active blend weights. This is self-normalizing: a solo animation plays at normal speed.</para>
        /// <para><b>Note:</b> If you apply <see cref="Godot.AnimationNodeTimeSeek"/> to the result when handling animations of different lengths, synchronization will be broken. In such cases, it is recommended to use <see cref="Godot.AnimationNodeAnimation.UseCustomTimeline"/> to align the animation lengths.</para>
        /// </summary>
        CyclicMutable = 2,
        /// <summary>
        /// <para>All animations are time-scaled so they complete one cycle in <see cref="Godot.AnimationNodeBlendSpace1D.CyclicLength"/> seconds, keeping them in sync regardless of their individual lengths.</para>
        /// <para><b>Note:</b> If you apply <see cref="Godot.AnimationNodeTimeSeek"/> to the result when handling animations of different lengths, synchronization will be broken. In such cases, it is recommended to use <see cref="Godot.AnimationNodeAnimation.UseCustomTimeline"/> to align the animation lengths.</para>
        /// </summary>
        CyclicConstant = 3
    }

    /// <summary>
    /// <para>The blend space's axis's lower limit for the points' position. See <see cref="Godot.AnimationNodeBlendSpace1D.AddBlendPoint(AnimationRootNode, float, int, StringName)"/>.</para>
    /// </summary>
    public float MinSpace
    {
        get
        {
            return GetMinSpace();
        }
        set
        {
            SetMinSpace(value);
        }
    }

    /// <summary>
    /// <para>The blend space's axis's upper limit for the points' position. See <see cref="Godot.AnimationNodeBlendSpace1D.AddBlendPoint(AnimationRootNode, float, int, StringName)"/>.</para>
    /// </summary>
    public float MaxSpace
    {
        get
        {
            return GetMaxSpace();
        }
        set
        {
            SetMaxSpace(value);
        }
    }

    /// <summary>
    /// <para>Position increment to snap to when moving a point on the axis.</para>
    /// </summary>
    public float Snap
    {
        get
        {
            return GetSnap();
        }
        set
        {
            SetSnap(value);
        }
    }

    /// <summary>
    /// <para>Label of the virtual axis of the blend space.</para>
    /// </summary>
    public string ValueLabel
    {
        get
        {
            return GetValueLabel();
        }
        set
        {
            SetValueLabel(value);
        }
    }

    /// <summary>
    /// <para>Controls the interpolation between animations.</para>
    /// </summary>
    public AnimationNodeBlendSpace1D.BlendModeEnum BlendMode
    {
        get
        {
            return GetBlendMode();
        }
        set
        {
            SetBlendMode(value);
        }
    }

    /// <summary>
    /// <para>If <see langword="true"/>, sync mode is enabled (equivalent to <see cref="Godot.AnimationNodeBlendSpace1D.SyncModeEnum.Independent"/>). This property is kept for backward compatibility.</para>
    /// </summary>
    [Obsolete("Use 'Godot.AnimationNodeBlendSpace1D.SyncMode' instead.")]
    public bool Sync
    {
        get
        {
            return IsUsingSync();
        }
        set
        {
            SetUseSync(value);
        }
    }

    /// <summary>
    /// <para>Controls how animations are synced when blended. See <see cref="Godot.AnimationNodeBlendSpace1D.SyncModeEnum"/> for available options.</para>
    /// </summary>
    public AnimationNodeBlendSpace1D.SyncModeEnum SyncMode
    {
        get
        {
            return GetSyncMode();
        }
        set
        {
            SetSyncMode(value);
        }
    }

    /// <summary>
    /// <para>The cycle length in seconds used by <see cref="Godot.AnimationNodeBlendSpace1D.SyncModeEnum.CyclicConstant"/>. All animations are time-scaled so they complete one full cycle in this duration. Must be greater than <c>0</c> for cyclic sync to take effect.</para>
    /// </summary>
    public double CyclicLength
    {
        get
        {
            return GetCyclicLength();
        }
        set
        {
            SetCyclicLength(value);
        }
    }

    private static readonly System.Type CachedType = typeof(AnimationNodeBlendSpace1D);

    private static readonly StringName NativeName = "AnimationNodeBlendSpace1D";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public AnimationNodeBlendSpace1D() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal AnimationNodeBlendSpace1D(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal AnimationNodeBlendSpace1D(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.AddBlendPoint, 398361042ul);

    /// <summary>
    /// <para>Adds a new point with <paramref name="name"/> that represents a <paramref name="node"/> on the virtual axis at a given position set by <paramref name="pos"/>. You can insert it at a specific index using the <paramref name="atIndex"/> argument. If you use the default value for <paramref name="atIndex"/>, the point is inserted at the end of the blend points array.</para>
    /// <para><b>Note:</b> If no name is provided, safe index is used as reference. In the future, empty names will be deprecated, so explicitly passing a name is recommended.</para>
    /// </summary>
    public void AddBlendPoint(AnimationRootNode node, float pos, int atIndex = -1, StringName name = null)
    {
        NativeCalls.godot_icall_4_169(MethodBind0, GodotObject.GetPtr(this), GodotObject.GetPtr(node), pos, atIndex, (godot_string_name)(name?.NativeValue ?? default));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetBlendPointPosition, 1602489585ul);

    /// <summary>
    /// <para>Updates the position of the point at index <paramref name="point"/> on the blend axis.</para>
    /// </summary>
    public void SetBlendPointPosition(int point, float pos)
    {
        NativeCalls.godot_icall_2_93(MethodBind1, GodotObject.GetPtr(this), point, pos);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetBlendPointPosition, 2339986948ul);

    /// <summary>
    /// <para>Returns the position of the point at index <paramref name="point"/>.</para>
    /// </summary>
    public float GetBlendPointPosition(int point)
    {
        float ret = NativeCalls.godot_icall_1_96(MethodBind2, GodotObject.GetPtr(this), point);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetBlendPointNode, 4240341528ul);

    /// <summary>
    /// <para>Changes the <see cref="Godot.AnimationNode"/> referenced by the point at index <paramref name="point"/>.</para>
    /// </summary>
    public void SetBlendPointNode(int point, AnimationRootNode node)
    {
        NativeCalls.godot_icall_2_94(MethodBind3, GodotObject.GetPtr(this), point, GodotObject.GetPtr(node));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetBlendPointNode, 665599029ul);

    /// <summary>
    /// <para>Returns the <see cref="Godot.AnimationNode"/> referenced by the point at index <paramref name="point"/>.</para>
    /// </summary>
    public AnimationRootNode GetBlendPointNode(int point)
    {
        AnimationRootNode ret = (AnimationRootNode)NativeCalls.godot_icall_1_95(MethodBind4, GodotObject.GetPtr(this), point);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetBlendPointName, 3780747571ul);

    /// <summary>
    /// <para>Sets the name of the blend point at index <paramref name="point"/>. If the name conflicts with an existing point, a unique name will be generated automatically.</para>
    /// </summary>
    public void SetBlendPointName(int point, StringName name)
    {
        NativeCalls.godot_icall_2_170(MethodBind5, GodotObject.GetPtr(this), point, (godot_string_name)(name?.NativeValue ?? default));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetBlendPointName, 659327637ul);

    /// <summary>
    /// <para>Returns the name of the blend point at index <paramref name="point"/>.</para>
    /// </summary>
    public StringName GetBlendPointName(int point)
    {
        StringName ret = NativeCalls.godot_icall_1_171(MethodBind6, GodotObject.GetPtr(this), point);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = ClassDB_get_method_with_compatibility(NativeName, MethodName.FindBlendPointByName, 2458036349ul);

    /// <summary>
    /// <para>Returns the index of the blend point with the given <paramref name="name"/>. Returns <c>-1</c> if no blend point with that name is found.</para>
    /// </summary>
    public int FindBlendPointByName(StringName name)
    {
        int ret = NativeCalls.godot_icall_1_172(MethodBind7, GodotObject.GetPtr(this), (godot_string_name)(name?.NativeValue ?? default));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind8 = ClassDB_get_method_with_compatibility(NativeName, MethodName.RemoveBlendPoint, 1286410249ul);

    /// <summary>
    /// <para>Removes the point at index <paramref name="point"/> from the blend axis.</para>
    /// </summary>
    public void RemoveBlendPoint(int point)
    {
        NativeCalls.godot_icall_1_38(MethodBind8, GodotObject.GetPtr(this), point);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind9 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetBlendPointCount, 3905245786ul);

    /// <summary>
    /// <para>Returns the number of points on the blend axis.</para>
    /// </summary>
    public int GetBlendPointCount()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind9, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind10 = ClassDB_get_method_with_compatibility(NativeName, MethodName.ReorderBlendPoint, 3937882851ul);

    /// <summary>
    /// <para>Swaps the blend points at indices <paramref name="fromIndex"/> and <paramref name="toIndex"/>, exchanging their positions and properties.</para>
    /// </summary>
    public void ReorderBlendPoint(int fromIndex, int toIndex)
    {
        NativeCalls.godot_icall_2_84(MethodBind10, GodotObject.GetPtr(this), fromIndex, toIndex);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind11 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetMinSpace, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetMinSpace(float minSpace)
    {
        NativeCalls.godot_icall_1_91(MethodBind11, GodotObject.GetPtr(this), minSpace);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind12 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMinSpace, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetMinSpace()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind12, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind13 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetMaxSpace, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetMaxSpace(float maxSpace)
    {
        NativeCalls.godot_icall_1_91(MethodBind13, GodotObject.GetPtr(this), maxSpace);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind14 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMaxSpace, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetMaxSpace()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind14, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind15 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetSnap, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetSnap(float snap)
    {
        NativeCalls.godot_icall_1_91(MethodBind15, GodotObject.GetPtr(this), snap);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind16 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetSnap, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetSnap()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind16, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind17 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetValueLabel, 83702148ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetValueLabel(string text)
    {
        NativeCalls.godot_icall_1_57(MethodBind17, GodotObject.GetPtr(this), text);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind18 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetValueLabel, 201670096ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public string GetValueLabel()
    {
        string ret = NativeCalls.godot_icall_0_58(MethodBind18, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind19 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetBlendMode, 2600869457ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetBlendMode(AnimationNodeBlendSpace1D.BlendModeEnum mode)
    {
        NativeCalls.godot_icall_1_38(MethodBind19, GodotObject.GetPtr(this), (int)mode);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind20 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetBlendMode, 1547667849ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public AnimationNodeBlendSpace1D.BlendModeEnum GetBlendMode()
    {
        AnimationNodeBlendSpace1D.BlendModeEnum ret = (AnimationNodeBlendSpace1D.BlendModeEnum)NativeCalls.godot_icall_0_39(MethodBind20, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind21 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetUseSync, 2586408642ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetUseSync(bool enable)
    {
        NativeCalls.godot_icall_1_14(MethodBind21, GodotObject.GetPtr(this), enable.ToGodotBool());
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind22 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsUsingSync, 36873697ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public bool IsUsingSync()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind22, GodotObject.GetPtr(this)).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind23 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetSyncMode, 1065895142ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetSyncMode(AnimationNodeBlendSpace1D.SyncModeEnum syncMode)
    {
        NativeCalls.godot_icall_1_38(MethodBind23, GodotObject.GetPtr(this), (int)syncMode);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind24 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetSyncMode, 132474921ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public AnimationNodeBlendSpace1D.SyncModeEnum GetSyncMode()
    {
        AnimationNodeBlendSpace1D.SyncModeEnum ret = (AnimationNodeBlendSpace1D.SyncModeEnum)NativeCalls.godot_icall_0_39(MethodBind24, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind25 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetCyclicLength, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetCyclicLength(double length)
    {
        NativeCalls.godot_icall_1_135(MethodBind25, GodotObject.GetPtr(this), length);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind26 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetCyclicLength, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public double GetCyclicLength()
    {
        double ret = NativeCalls.godot_icall_0_136(MethodBind26, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind27 = ClassDB_get_method_with_compatibility(NativeName, MethodName.AddBlendPoint, 285050433ul);

    /// <summary>
    /// <para>Adds a new point with <paramref name="name"/> that represents a <paramref name="node"/> on the virtual axis at a given position set by <paramref name="pos"/>. You can insert it at a specific index using the <paramref name="atIndex"/> argument. If you use the default value for <paramref name="atIndex"/>, the point is inserted at the end of the blend points array.</para>
    /// <para><b>Note:</b> If no name is provided, safe index is used as reference. In the future, empty names will be deprecated, so explicitly passing a name is recommended.</para>
    /// </summary>
    [EditorBrowsable(EditorBrowsableState.Never)]
    public void AddBlendPoint(AnimationRootNode node, float pos, int atIndex)
    {
        NativeCalls.godot_icall_3_173(MethodBind27, GodotObject.GetPtr(this), GodotObject.GetPtr(node), pos, atIndex);
        global::System.GC.KeepAlive(this);
    }

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
        return base.HasGodotClassSignal(signal);
    }

    /// <summary>
    /// Cached StringNames for the properties and fields contained in this class, for fast lookup.
    /// </summary>
    public new class PropertyName : AnimationRootNode.PropertyName
    {
        /// <summary>
        /// Cached name for the 'min_space' property.
        /// </summary>
        public static readonly StringName MinSpace = "min_space";
        /// <summary>
        /// Cached name for the 'max_space' property.
        /// </summary>
        public static readonly StringName MaxSpace = "max_space";
        /// <summary>
        /// Cached name for the 'snap' property.
        /// </summary>
        public static readonly StringName Snap = "snap";
        /// <summary>
        /// Cached name for the 'value_label' property.
        /// </summary>
        public static readonly StringName ValueLabel = "value_label";
        /// <summary>
        /// Cached name for the 'blend_mode' property.
        /// </summary>
        public static readonly StringName BlendMode = "blend_mode";
        /// <summary>
        /// Cached name for the 'sync' property.
        /// </summary>
        public static readonly StringName Sync = "sync";
        /// <summary>
        /// Cached name for the 'sync_mode' property.
        /// </summary>
        public static readonly StringName SyncMode = "sync_mode";
        /// <summary>
        /// Cached name for the 'cyclic_length' property.
        /// </summary>
        public static readonly StringName CyclicLength = "cyclic_length";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : AnimationRootNode.MethodName
    {
        /// <summary>
        /// Cached name for the 'add_blend_point' method.
        /// </summary>
        public static readonly StringName AddBlendPoint = "add_blend_point";
        /// <summary>
        /// Cached name for the 'set_blend_point_position' method.
        /// </summary>
        public static readonly StringName SetBlendPointPosition = "set_blend_point_position";
        /// <summary>
        /// Cached name for the 'get_blend_point_position' method.
        /// </summary>
        public static readonly StringName GetBlendPointPosition = "get_blend_point_position";
        /// <summary>
        /// Cached name for the 'set_blend_point_node' method.
        /// </summary>
        public static readonly StringName SetBlendPointNode = "set_blend_point_node";
        /// <summary>
        /// Cached name for the 'get_blend_point_node' method.
        /// </summary>
        public static readonly StringName GetBlendPointNode = "get_blend_point_node";
        /// <summary>
        /// Cached name for the 'set_blend_point_name' method.
        /// </summary>
        public static readonly StringName SetBlendPointName = "set_blend_point_name";
        /// <summary>
        /// Cached name for the 'get_blend_point_name' method.
        /// </summary>
        public static readonly StringName GetBlendPointName = "get_blend_point_name";
        /// <summary>
        /// Cached name for the 'find_blend_point_by_name' method.
        /// </summary>
        public static readonly StringName FindBlendPointByName = "find_blend_point_by_name";
        /// <summary>
        /// Cached name for the 'remove_blend_point' method.
        /// </summary>
        public static readonly StringName RemoveBlendPoint = "remove_blend_point";
        /// <summary>
        /// Cached name for the 'get_blend_point_count' method.
        /// </summary>
        public static readonly StringName GetBlendPointCount = "get_blend_point_count";
        /// <summary>
        /// Cached name for the 'reorder_blend_point' method.
        /// </summary>
        public static readonly StringName ReorderBlendPoint = "reorder_blend_point";
        /// <summary>
        /// Cached name for the 'set_min_space' method.
        /// </summary>
        public static readonly StringName SetMinSpace = "set_min_space";
        /// <summary>
        /// Cached name for the 'get_min_space' method.
        /// </summary>
        public static readonly StringName GetMinSpace = "get_min_space";
        /// <summary>
        /// Cached name for the 'set_max_space' method.
        /// </summary>
        public static readonly StringName SetMaxSpace = "set_max_space";
        /// <summary>
        /// Cached name for the 'get_max_space' method.
        /// </summary>
        public static readonly StringName GetMaxSpace = "get_max_space";
        /// <summary>
        /// Cached name for the 'set_snap' method.
        /// </summary>
        public static readonly StringName SetSnap = "set_snap";
        /// <summary>
        /// Cached name for the 'get_snap' method.
        /// </summary>
        public static readonly StringName GetSnap = "get_snap";
        /// <summary>
        /// Cached name for the 'set_value_label' method.
        /// </summary>
        public static readonly StringName SetValueLabel = "set_value_label";
        /// <summary>
        /// Cached name for the 'get_value_label' method.
        /// </summary>
        public static readonly StringName GetValueLabel = "get_value_label";
        /// <summary>
        /// Cached name for the 'set_blend_mode' method.
        /// </summary>
        public static readonly StringName SetBlendMode = "set_blend_mode";
        /// <summary>
        /// Cached name for the 'get_blend_mode' method.
        /// </summary>
        public static readonly StringName GetBlendMode = "get_blend_mode";
        /// <summary>
        /// Cached name for the 'set_use_sync' method.
        /// </summary>
        public static readonly StringName SetUseSync = "set_use_sync";
        /// <summary>
        /// Cached name for the 'is_using_sync' method.
        /// </summary>
        public static readonly StringName IsUsingSync = "is_using_sync";
        /// <summary>
        /// Cached name for the 'set_sync_mode' method.
        /// </summary>
        public static readonly StringName SetSyncMode = "set_sync_mode";
        /// <summary>
        /// Cached name for the 'get_sync_mode' method.
        /// </summary>
        public static readonly StringName GetSyncMode = "get_sync_mode";
        /// <summary>
        /// Cached name for the 'set_cyclic_length' method.
        /// </summary>
        public static readonly StringName SetCyclicLength = "set_cyclic_length";
        /// <summary>
        /// Cached name for the 'get_cyclic_length' method.
        /// </summary>
        public static readonly StringName GetCyclicLength = "get_cyclic_length";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : AnimationRootNode.SignalName
    {
    }
}
