#!/bin/bash

# Environment variables
export OPENAI_API_KEY="sk-b31163473c6b401b8d0787163862828c"
export ZHIPUAI_API_KEY="218e3a528b01450ab8f81076ad412e27.J2jy1HLW2jhW2ghr"
export OPENAI_API_KEY_YI="sk-S3CJ5RZqrEiYycs538Ce9164C3E74bF18a201e6b591f2b93"
export OPENAI_API_KEY_VIP="sk-gAedAIHwjEhdDA8u9l8OTBGI5XYVyAXMNe4WbtUyLcuC7OzL"
export ALPHA_VANTAGE_API_KEY="C31J8L3MVVRY7JM7"
export OPENAI_API_KEY_DS="sk-8d31e06e931d4bbd92ae3b2f2bd1e86c"
export FRED_API_KEY="a51dd5db3dd92839ed846e761e299ffe"
export PLAN_API_KEY="sk-sp-4a365c8a13f74fae8b513a0c02300bdd"
export DY_API_KEY="b3c3332c-faa9-40d4-8bd7-aed36bb04fa4"
export CL_API_KET="sk-y5lueeZ66Ty3kU8fMOKVW3FJuETSfKqpCNXoVrbZI7bpv1V4"
export XIAOCHI_API_KEY="sk-3pjhBWGy2expXnpNEwbafnhcDt2NMbAQJETvAuqHTxUKNrag"
export REN_API_KEY="sk-R6Ipj1CaAsAvhmGdlIrpZIq2Vtx9E3l6a9jwnH8c3ivZuOEb"
# Usage:
#   Normal mode (default):  bash run.sh
#   Complex mode:           bash run.sh --complex
#   With concurrency:       bash run.sh --max-workers 3
#   Layout workers:         bash run.sh --layout-max-workers 4
#   Scene workers:          bash run.sh --scene-max-workers 2
#   Print layout debug:     bash run.sh --enable-print-layout
#   Print scene debug:      bash run.sh --enable-print-scene
#   Concept graph mode:     bash run.sh --enable-concept-graph
#   Combine modes:          bash run.sh --enable-concept-graph --enable-print-layout
conda activate svg
# Run video enhancer
# python video_enhancer.py /home/ubuntu/sysu/svgagent/video/futureai.mp4 \
#     --llm kimi-k2.5 \
#     --vision-llm kimi-k2.5 \
#     --max-workers 10 \
#     "$@"

# python video_enhancer.py /home/ubuntu/sysu/svgagent/video/ted1.mp4 \
#     --llm glm-5 \
#     --vision-llm qwen3.5-plus \
#     --max-workers 10 \
#     --svg-mode simple \
#     --layout-max-workers 6 \
#     --scene-max-workers 3 \
#     --enable-concept-graph \
#     --enable-print-layout \
#     "$@"


# python video_enhancer.py /home/ubuntu/sysu/svgagent/video/altman.mp4 \
#     --llm gemini-3.1-pro-high \
#     --vision-llm gemini-3.1-pro-high \
#     --svg-mode simple \
#     --max-workers 5 \
#     --layout-max-workers 6 \
#     --scene-max-workers 3 \
#     "$@" 

# python video_enhancer.py /home/ubuntu/sysu/svgagent/video/ted1.mp4 \
#     --llm gpt-5.4  \
#     --vision-llm gpt-5.4  \
#     --max-workers 10 \
#     --svg-mode simple \
#     --layout-max-workers 6 \
#     --scene-max-workers 3 \
#     --enable-concept-graph \
#     "$@"

# python video_enhancer.py /home/ubuntu/sysu/svgagent/video/ted1.mp4 \
#     --llm gemini-3.1-pro  \
#     --vision-llm gemini-3.1-pro  \
#     --max-workers 10 \
#     --svg-mode simple \
#     --layout-max-workers 6 \
#     --scene-max-workers 3 \
#     --enable-concept-graph \
#     "$@"


# python video_enhancer.py /home/ubuntu/sysu/svgagent/video/1.mp4 \
#     --llm gemini-3.1-pro-high \
#     --vision-llm gemini-3.1-pro-high \
#     --svg-mode simple \
#     --max-workers 5 \
#     --layout-max-workers 6 \
#     --scene-max-workers 3 \
#     "$@" 

python video_enhancer.py /home/ubuntu/sysu/svgagent/video/2.mp4 \
    --llm gemini-3.1-pro-high \
    --vision-llm gemini-3.1-pro-high \
    --svg-mode simple \
    --max-workers 5 \
    --layout-max-workers 6 \
    --scene-max-workers 3 \
    "$@" 

python video_enhancer.py /home/ubuntu/sysu/svgagent/video/3.mp4 \
    --llm gemini-3.1-pro-high \
    --vision-llm gemini-3.1-pro-high \
    --svg-mode simple \
    --max-workers 5 \
    --layout-max-workers 6 \
    --scene-max-workers 3 \
    "$@" 

python video_enhancer.py /home/ubuntu/sysu/svgagent/video/4.mp4 \
    --llm gemini-3.1-pro-high \
    --vision-llm gemini-3.1-pro-high \
    --svg-mode simple \
    --max-workers 5 \
    --layout-max-workers 6 \
    --scene-max-workers 3 \
    "$@" 

python video_enhancer.py /home/ubuntu/sysu/svgagent/video/5.mp4 \
    --llm gemini-3.1-pro-high \
    --vision-llm gemini-3.1-pro-high \
    --svg-mode simple \
    --max-workers 5 \
    --layout-max-workers 6 \
    --scene-max-workers 3 \
    "$@" 

python video_enhancer.py /home/ubuntu/sysu/svgagent/video/6.mp4 \
    --llm gemini-3.1-pro-high \
    --vision-llm gemini-3.1-pro-high \
    --svg-mode simple \
    --max-workers 5 \
    --layout-max-workers 6 \
    --scene-max-workers 3 \
    "$@" 

python video_enhancer.py /home/ubuntu/sysu/svgagent/video/7.mp4 \
    --llm gemini-3.1-pro-high \
    --vision-llm gemini-3.1-pro-high \
    --svg-mode simple \
    --max-workers 5 \
    --layout-max-workers 6 \
    --scene-max-workers 3 \
    "$@" 

python video_enhancer.py /home/ubuntu/sysu/svgagent/video/8.mp4 \
    --llm gemini-3.1-pro-high \
    --vision-llm gemini-3.1-pro-high \
    --svg-mode simple \
    --max-workers 5 \
    --layout-max-workers 6 \
    --scene-max-workers 3 \
    "$@" 

python video_enhancer.py /home/ubuntu/sysu/svgagent/video/9.mp4 \
    --llm gemini-3.1-pro-high \
    --vision-llm gemini-3.1-pro-high \
    --svg-mode simple \
    --max-workers 5 \
    --layout-max-workers 6 \
    --scene-max-workers 3 \
    "$@" 


python video_enhancer.py /home/ubuntu/sysu/svgagent/video/10.mp4 \
    --llm gemini-3.1-pro-high \
    --vision-llm gemini-3.1-pro-high \
    --svg-mode simple \
    --max-workers 5 \
    --layout-max-workers 6 \
    --scene-max-workers 3 \
    "$@" 

