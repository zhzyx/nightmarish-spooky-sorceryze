#[compute]

#version 450

#VERSION_DEFINES

// Finalizes the terrain indirect draw arguments from the atomic counter and resets the
// counter for the next frame (self-clearing, no buffer clears needed).

layout(local_size_x = 1, local_size_y = 1, local_size_z = 1) in;

#ifndef NATIVE_MULTIMESH
layout(set = 0, binding = 0, std430) buffer restrict Counter {
	uint counter;
}
counter_buf;
#endif

layout(set = 0, binding = 1, std430) buffer restrict Args {
	uint args[5];
}
args_buf;

#ifndef NATIVE_MULTIMESH
layout(set = 0, binding = 2, std430) buffer restrict ShadowArgs {
	uint args[5];
}
shadow_args_buf;
#endif

layout(push_constant, std430) uniform Params {
	uint index_count;
	uint max_instances;
	uint pad1;
	uint pad2;
}
params;

#ifdef NATIVE_MULTIMESH
layout(set = 0, binding = 3, std430) buffer Compaction { uvec4 groups[]; } compaction;
#endif

void main() {
#ifdef NATIVE_MULTIMESH
	uint group_count = params.pad1;
	uint block_count = (group_count + 255u) / 256u;
	if (params.pad2 == 0u) {
		uint block = gl_GlobalInvocationID.x;
		uint begin = block * 256u;
		uint sum = 0u;
		for (uint i = begin; i < min(begin + 256u, group_count); ++i) {
			compaction.groups[i].w = sum;
			sum += compaction.groups[i].z;
		}
		compaction.groups[group_count + block].z = sum;
		return;
	}
	uint count = 0u;
	for (uint i = 0u; i < block_count; ++i) {
		compaction.groups[group_count + i].w = count;
		count += compaction.groups[group_count + i].z;
	}
	args_buf.args[1] = min(count, params.max_instances);
#else
	uint count = min(counter_buf.counter, params.max_instances);
#ifndef NATIVE_MULTIMESH
	args_buf.args[0] = params.index_count;
	args_buf.args[2] = 0u;
	args_buf.args[3] = 0u;
	args_buf.args[4] = 0u;
	shadow_args_buf.args[0] = params.index_count;
	shadow_args_buf.args[1] = count;
	shadow_args_buf.args[2] = 0u;
	shadow_args_buf.args[3] = 0u;
	shadow_args_buf.args[4] = 0u;
#endif
	args_buf.args[1] = count;
	counter_buf.counter = 0u;
#endif
}
