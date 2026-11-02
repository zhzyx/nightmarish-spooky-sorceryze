# Local SCons configuration, picked up automatically by SConstruct and therefore
# shared by manual builds, the in-editor "build and update engine" button and any
# agent-driven build. This fork tracks the configuration as a build input.

# The prebuilt ANGLE static libraries shipped by godot-angle-static are compiled
# with a newer MSVC toolset than the ones installed here (14.38 and 14.44). They
# reference MSVC STL vectorized helpers -- __std_max_element_4i, __std_rotate,
# __std_min_element_8u, __std_max_element_f_, __std_find_first_not_of_trivial_pos_1
# and __std_find_last_not_of_trivial_pos_1 -- that are absent from both libcpmt.lib
# and msvcprt.lib of those toolsets, so linking the editor fails with LNK2019 and
# LNK1120. ANGLE only backs the OpenGL-over-Direct3D11 fallback of the
# Compatibility renderer, which this development editor does not rely on, so it is
# disabled locally. Re-enable it (and update Visual Studio) before producing
# Windows release builds, where that driver fallback does matter.
angle = "no"
