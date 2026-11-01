namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
public partial class FuzzySearchMatch : RefCounted
{
    /// <summary>
    /// <para>Target string which was matched against.</para>
    /// </summary>
    public string Target
    {
        get
        {
            return GetTarget();
        }
        set
        {
            SetTarget(value);
        }
    }

    /// <summary>
    /// <para>Match score determined by <see cref="Godot.FuzzySearch"/>. Scores are not normalized and generally should not be directly compared between different queries.</para>
    /// </summary>
    public int Score
    {
        get
        {
            return GetScore();
        }
        set
        {
            SetScore(value);
        }
    }

    /// <summary>
    /// <para>The original index of <see cref="Godot.FuzzySearchMatch.Target"/> in the provided array of targets when using <see cref="Godot.FuzzySearch.SearchAll(string, string[])"/> otherwise <c>-1</c>.</para>
    /// </summary>
    public int OriginalIndex
    {
        get
        {
            return GetOriginalIndex();
        }
        set
        {
            SetOriginalIndex(value);
        }
    }

    private static readonly System.Type CachedType = typeof(FuzzySearchMatch);

    private static readonly StringName NativeName = "FuzzySearchMatch";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public FuzzySearchMatch() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal FuzzySearchMatch(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal FuzzySearchMatch(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetTarget, 83702148ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetTarget(string target)
    {
        NativeCalls.godot_icall_1_57(MethodBind0, GodotObject.GetPtr(this), target);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetTarget, 201670096ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public string GetTarget()
    {
        string ret = NativeCalls.godot_icall_0_58(MethodBind1, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetScore, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetScore(int score)
    {
        NativeCalls.godot_icall_1_38(MethodBind2, GodotObject.GetPtr(this), score);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetScore, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public int GetScore()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind3, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetOriginalIndex, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetOriginalIndex(int originalIndex)
    {
        NativeCalls.godot_icall_1_38(MethodBind4, GodotObject.GetPtr(this), originalIndex);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetOriginalIndex, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public int GetOriginalIndex()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind5, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMatchedSubstrings, 3995934104ul);

    /// <summary>
    /// <para>Returns each matched substring interval of <see cref="Godot.FuzzySearchMatch.Target"/>. The <c>Vector2i.x</c> component is the start of the interval and the <c>Vector2i.y</c> component is the length, corresponding to the arguments for <c>String.substr</c>.</para>
    /// </summary>
    public Godot.Collections.Array<Vector2I> GetMatchedSubstrings()
    {
        Godot.Collections.Array<Vector2I> ret = new Godot.Collections.Array<Vector2I>(NativeCalls.godot_icall_0_146(MethodBind6, GodotObject.GetPtr(this)));
        global::System.GC.KeepAlive(this);
        return ret;
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
    public new class PropertyName : RefCounted.PropertyName
    {
        /// <summary>
        /// Cached name for the 'target' property.
        /// </summary>
        public static readonly StringName Target = "target";
        /// <summary>
        /// Cached name for the 'score' property.
        /// </summary>
        public static readonly StringName Score = "score";
        /// <summary>
        /// Cached name for the 'original_index' property.
        /// </summary>
        public static readonly StringName OriginalIndex = "original_index";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : RefCounted.MethodName
    {
        /// <summary>
        /// Cached name for the 'set_target' method.
        /// </summary>
        public static readonly StringName SetTarget = "set_target";
        /// <summary>
        /// Cached name for the 'get_target' method.
        /// </summary>
        public static readonly StringName GetTarget = "get_target";
        /// <summary>
        /// Cached name for the 'set_score' method.
        /// </summary>
        public static readonly StringName SetScore = "set_score";
        /// <summary>
        /// Cached name for the 'get_score' method.
        /// </summary>
        public static readonly StringName GetScore = "get_score";
        /// <summary>
        /// Cached name for the 'set_original_index' method.
        /// </summary>
        public static readonly StringName SetOriginalIndex = "set_original_index";
        /// <summary>
        /// Cached name for the 'get_original_index' method.
        /// </summary>
        public static readonly StringName GetOriginalIndex = "get_original_index";
        /// <summary>
        /// Cached name for the 'get_matched_substrings' method.
        /// </summary>
        public static readonly StringName GetMatchedSubstrings = "get_matched_substrings";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : RefCounted.SignalName
    {
    }
}
