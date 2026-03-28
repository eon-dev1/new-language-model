#!/bin/bash
#
# NLM Local LLM Server Startup Script
# Starts llama.cpp server with Granite 4 Tiny model for agentic tool calling
#

set -e

# Base paths
NLM_ROOT="/filepath/NLM"
LLAMA_CPP="${NLM_ROOT}/llama.cpp"
LOCAL_LLM="${NLM_ROOT}/local_llm"

# Model configuration
MODEL_PATH="filepath.gguf"
CHAT_TEMPLATE="${LLAMA_CPP}/models/templates/tool-calling-model.jinja"

# Server configuration
HOST="127.0.0.1"
PORT="8080"
CONTEXT_SIZE="131072"      # 128K context window
GPU_LAYERS="99"            # Offload all layers to GPU
BATCH_SIZE="4096"
UBATCH_SIZE="8192"
PARALLEL_SLOTS="1"

# Logging
LOG_DIR="${LOCAL_LLM}/logs"
LOG_FILE="${LOG_DIR}/granite-server.log"

# Create log directory if it doesn't exist
mkdir -p "${LOG_DIR}"

# Check if server binary exists
# Check your GPU architecture, not all will use blackwell SM 120 
SERVER_BIN="${LLAMA_CPP}/build/bin/llama-server"
if [[ ! -x "${SERVER_BIN}" ]]; then
    echo "Error: llama-server binary not found at ${SERVER_BIN}"
    echo "Please build llama.cpp first:"
    echo "  cd ${LLAMA_CPP}/build"
    echo "  cmake .. -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=\"120\" -DLLAMA_CURL=OFF"
    echo "  make -j\$(nproc)"
    exit 1
fi

# Check if model exists
if [[ ! -f "${MODEL_PATH}" ]]; then
    echo "Error: Model not found at ${MODEL_PATH}"
    exit 1
fi

# Check if chat template exists
if [[ ! -f "${CHAT_TEMPLATE}" ]]; then
    echo "Warning: Chat template not found at ${CHAT_TEMPLATE}"
    echo "Proceeding without custom template (using model default)"
    TEMPLATE_ARG=""
else
    TEMPLATE_ARG="--chat-template-file ${CHAT_TEMPLATE}"
fi

echo "Starting NLM Local LLM Server..."
echo "  Model: $(basename ${MODEL_PATH})"
echo "  Host: ${HOST}:${PORT}"
echo "  Context: ${CONTEXT_SIZE} tokens"
echo "  GPU Layers: ${GPU_LAYERS}"
echo "  Log: ${LOG_FILE}"
echo ""

# Start the server
exec "${SERVER_BIN}" \
    -m "${MODEL_PATH}" \
    ${TEMPLATE_ARG} \
    -c "${CONTEXT_SIZE}" \
    -ngl "${GPU_LAYERS}" \
    -ub "${UBATCH_SIZE}" \
    --batch-size "${BATCH_SIZE}" \
    --parallel "${PARALLEL_SLOTS}" \
    --host "${HOST}" \
    --port "${PORT}" \
    --jinja \
    2>&1 | tee "${LOG_FILE}"
