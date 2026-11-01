namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>The fuzzy search algorithm is designed to find target strings which mostly match a query string while allowing for breaks, typos, and out of order matches.</para>
/// <para><code>
/// string[] items = ["Potion of Healing", "Greater Health Potion", "Poison Vial"];
/// FuzzySearch fuzzy = new();
/// 
/// foreach (var result in fuzzy.SearchAll("health potion", items))
/// {
/// 	// Prints "Greater Health Potion", "Potion of Healing"
/// 	GD.Print(result.Target);
/// }
/// </code></para>
/// </summary>
public partial class FuzzySearch : RefCounted
{
    /// <summary>
    /// <para>Number of leading characters to omit from matching. For example, this can be used to skip a common prefix such as <c>res://</c>.</para>
    /// </summary>
    public int StartOffset
    {
        get
        {
            return GetStartOffset();
        }
        set
        {
            SetStartOffset(value);
        }
    }

    /// <summary>
    /// <para>Maximum number of results which can be returned by <see cref="Godot.FuzzySearch.SearchAll(string, string[])"/>.</para>
    /// </summary>
    public int MaxResults
    {
        get
        {
            return GetMaxResults();
        }
        set
        {
            SetMaxResults(value);
        }
    }

    /// <summary>
    /// <para>Maximum number of non-matched characters in the query before skipping a target as non-matching. This option is ignored if <see cref="Godot.FuzzySearch.UseExactTokens"/> is <see langword="true"/>.</para>
    /// </summary>
    public int MaxMisses
    {
        get
        {
            return GetMaxMisses();
        }
        set
        {
            SetMaxMisses(value);
        }
    }

    /// <summary>
    /// <para>If <see langword="true"/>, only targets which contain each token as a non-overlapping substring are returned. Gaps and missed characters are not considered valid matches, but <see cref="Godot.FuzzySearch.CaseSensitive"/> is still used.</para>
    /// </summary>
    public bool UseExactTokens
    {
        get
        {
            return GetUseExactTokens();
        }
        set
        {
            SetUseExactTokens(value);
        }
    }

    /// <summary>
    /// <para>Whether the query character casing should be matched exactly or not.</para>
    /// </summary>
    public bool CaseSensitive
    {
        get
        {
            return GetCaseSensitive();
        }
        set
        {
            SetCaseSensitive(value);
        }
    }

    /// <summary>
    /// <para>If <see langword="true"/>, lower quality matches are not returned by <see cref="Godot.FuzzySearch.SearchAll(string, string[])"/>. The default filtering behavior is tuned to keep exact matches and reject significantly broken up matches. Setting this to <see langword="false"/> can potentially improve results when searching a small number of items.</para>
    /// </summary>
    public bool FilterLowScores
    {
        get
        {
            return GetFilterLowScores();
        }
        set
        {
            SetFilterLowScores(value);
        }
    }

    /// <summary>
    /// <para>Biases the filtering cutoff score between the average score and max score. Value should be between <c>0</c> and <c>1</c>.</para>
    /// </summary>
    public float FilterFactor
    {
        get
        {
            return GetFilterFactor();
        }
        set
        {
            SetFilterFactor(value);
        }
    }

    /// <summary>
    /// <para>Minimum score for filtering results returned by <see cref="Godot.FuzzySearch.SearchAll(string, string[])"/>.</para>
    /// </summary>
    public float FilterCutoff
    {
        get
        {
            return GetFilterCutoff();
        }
        set
        {
            SetFilterCutoff(value);
        }
    }

    private static readonly System.Type CachedType = typeof(FuzzySearch);

    private static readonly StringName NativeName = "FuzzySearch";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public FuzzySearch() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal FuzzySearch(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal FuzzySearch(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetStartOffset, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetStartOffset(int startOffset)
    {
        NativeCalls.godot_icall_1_38(MethodBind0, GodotObject.GetPtr(this), startOffset);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetStartOffset, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public int GetStartOffset()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind1, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetMaxResults, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetMaxResults(int maxResults)
    {
        NativeCalls.godot_icall_1_38(MethodBind2, GodotObject.GetPtr(this), maxResults);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMaxResults, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public int GetMaxResults()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind3, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetMaxMisses, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetMaxMisses(int maxMisses)
    {
        NativeCalls.godot_icall_1_38(MethodBind4, GodotObject.GetPtr(this), maxMisses);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMaxMisses, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public int GetMaxMisses()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind5, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetUseExactTokens, 2586408642ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetUseExactTokens(bool useExactTokens)
    {
        NativeCalls.godot_icall_1_14(MethodBind6, GodotObject.GetPtr(this), useExactTokens.ToGodotBool());
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetUseExactTokens, 36873697ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public bool GetUseExactTokens()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind7, GodotObject.GetPtr(this)).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind8 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetCaseSensitive, 2586408642ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetCaseSensitive(bool caseSensitive)
    {
        NativeCalls.godot_icall_1_14(MethodBind8, GodotObject.GetPtr(this), caseSensitive.ToGodotBool());
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind9 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetCaseSensitive, 36873697ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public bool GetCaseSensitive()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind9, GodotObject.GetPtr(this)).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind10 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetFilterLowScores, 2586408642ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetFilterLowScores(bool filterLowScores)
    {
        NativeCalls.godot_icall_1_14(MethodBind10, GodotObject.GetPtr(this), filterLowScores.ToGodotBool());
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind11 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetFilterLowScores, 36873697ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public bool GetFilterLowScores()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind11, GodotObject.GetPtr(this)).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind12 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetFilterFactor, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetFilterFactor(float filterFactor)
    {
        NativeCalls.godot_icall_1_91(MethodBind12, GodotObject.GetPtr(this), filterFactor);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind13 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetFilterFactor, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetFilterFactor()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind13, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind14 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetFilterCutoff, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetFilterCutoff(float filterCutoff)
    {
        NativeCalls.godot_icall_1_91(MethodBind14, GodotObject.GetPtr(this), filterCutoff);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind15 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetFilterCutoff, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetFilterCutoff()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind15, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind16 = ClassDB_get_method_with_compatibility(NativeName, MethodName.Search, 1830672150ul);

    /// <summary>
    /// <para>Searches the <paramref name="target"/> for <paramref name="query"/>, returning a <see cref="Godot.FuzzySearchMatch"/> instance on success or <see langword="null"/> otherwise.</para>
    /// </summary>
    public FuzzySearchMatch Search(string query, string target)
    {
        FuzzySearchMatch ret = (FuzzySearchMatch)NativeCalls.godot_icall_2_655(MethodBind16, GodotObject.GetPtr(this), query, target);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind17 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SearchAll, 4033994781ul);

    /// <summary>
    /// <para>Searches all of <paramref name="targets"/> for <paramref name="query"/> and returns up to the top <see cref="Godot.FuzzySearch.MaxResults"/> scoring values. The results are sorted by score in descending order. Low quality results are removed if <see cref="Godot.FuzzySearch.FilterLowScores"/> is <see langword="true"/>.</para>
    /// </summary>
    public Godot.Collections.Array<FuzzySearchMatch> SearchAll(string query, string[] targets)
    {
        Godot.Collections.Array<FuzzySearchMatch> ret = new Godot.Collections.Array<FuzzySearchMatch>(NativeCalls.godot_icall_2_656(MethodBind17, GodotObject.GetPtr(this), query, targets));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    /// <summary>
    /// <para>Searches all of <paramref name="targets"/> for <paramref name="query"/> and returns up to the top <see cref="Godot.FuzzySearch.MaxResults"/> scoring values. The results are sorted by score in descending order. Low quality results are removed if <see cref="Godot.FuzzySearch.FilterLowScores"/> is <see langword="true"/>.</para>
    /// </summary>
    public Godot.Collections.Array<FuzzySearchMatch> SearchAll(string query, ReadOnlySpan<string> targets)
    {
        Godot.Collections.Array<FuzzySearchMatch> ret = new Godot.Collections.Array<FuzzySearchMatch>(NativeCalls.godot_icall_2_656(MethodBind17, GodotObject.GetPtr(this), query, targets));
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
        /// Cached name for the 'start_offset' property.
        /// </summary>
        public static readonly StringName StartOffset = "start_offset";
        /// <summary>
        /// Cached name for the 'max_results' property.
        /// </summary>
        public static readonly StringName MaxResults = "max_results";
        /// <summary>
        /// Cached name for the 'max_misses' property.
        /// </summary>
        public static readonly StringName MaxMisses = "max_misses";
        /// <summary>
        /// Cached name for the 'use_exact_tokens' property.
        /// </summary>
        public static readonly StringName UseExactTokens = "use_exact_tokens";
        /// <summary>
        /// Cached name for the 'case_sensitive' property.
        /// </summary>
        public static readonly StringName CaseSensitive = "case_sensitive";
        /// <summary>
        /// Cached name for the 'filter_low_scores' property.
        /// </summary>
        public static readonly StringName FilterLowScores = "filter_low_scores";
        /// <summary>
        /// Cached name for the 'filter_factor' property.
        /// </summary>
        public static readonly StringName FilterFactor = "filter_factor";
        /// <summary>
        /// Cached name for the 'filter_cutoff' property.
        /// </summary>
        public static readonly StringName FilterCutoff = "filter_cutoff";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : RefCounted.MethodName
    {
        /// <summary>
        /// Cached name for the 'set_start_offset' method.
        /// </summary>
        public static readonly StringName SetStartOffset = "set_start_offset";
        /// <summary>
        /// Cached name for the 'get_start_offset' method.
        /// </summary>
        public static readonly StringName GetStartOffset = "get_start_offset";
        /// <summary>
        /// Cached name for the 'set_max_results' method.
        /// </summary>
        public static readonly StringName SetMaxResults = "set_max_results";
        /// <summary>
        /// Cached name for the 'get_max_results' method.
        /// </summary>
        public static readonly StringName GetMaxResults = "get_max_results";
        /// <summary>
        /// Cached name for the 'set_max_misses' method.
        /// </summary>
        public static readonly StringName SetMaxMisses = "set_max_misses";
        /// <summary>
        /// Cached name for the 'get_max_misses' method.
        /// </summary>
        public static readonly StringName GetMaxMisses = "get_max_misses";
        /// <summary>
        /// Cached name for the 'set_use_exact_tokens' method.
        /// </summary>
        public static readonly StringName SetUseExactTokens = "set_use_exact_tokens";
        /// <summary>
        /// Cached name for the 'get_use_exact_tokens' method.
        /// </summary>
        public static readonly StringName GetUseExactTokens = "get_use_exact_tokens";
        /// <summary>
        /// Cached name for the 'set_case_sensitive' method.
        /// </summary>
        public static readonly StringName SetCaseSensitive = "set_case_sensitive";
        /// <summary>
        /// Cached name for the 'get_case_sensitive' method.
        /// </summary>
        public static readonly StringName GetCaseSensitive = "get_case_sensitive";
        /// <summary>
        /// Cached name for the 'set_filter_low_scores' method.
        /// </summary>
        public static readonly StringName SetFilterLowScores = "set_filter_low_scores";
        /// <summary>
        /// Cached name for the 'get_filter_low_scores' method.
        /// </summary>
        public static readonly StringName GetFilterLowScores = "get_filter_low_scores";
        /// <summary>
        /// Cached name for the 'set_filter_factor' method.
        /// </summary>
        public static readonly StringName SetFilterFactor = "set_filter_factor";
        /// <summary>
        /// Cached name for the 'get_filter_factor' method.
        /// </summary>
        public static readonly StringName GetFilterFactor = "get_filter_factor";
        /// <summary>
        /// Cached name for the 'set_filter_cutoff' method.
        /// </summary>
        public static readonly StringName SetFilterCutoff = "set_filter_cutoff";
        /// <summary>
        /// Cached name for the 'get_filter_cutoff' method.
        /// </summary>
        public static readonly StringName GetFilterCutoff = "get_filter_cutoff";
        /// <summary>
        /// Cached name for the 'search' method.
        /// </summary>
        public static readonly StringName Search = "search";
        /// <summary>
        /// Cached name for the 'search_all' method.
        /// </summary>
        public static readonly StringName SearchAll = "search_all";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : RefCounted.SignalName
    {
    }
}
