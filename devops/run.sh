#/bin/bash -e

cmd="$1"
args="${@:2}"

echo "Running command: $cmd with args: $args"

pkill -9 -f wandb
pkill -9 -f python
git pull
cd deps/puffergrid && git pull && python setup.py build_ext --inplace && cd ../..
# cd deps/pufferlib && git pull && python setup.py build_ext --inplace && cd ../..
cd deps/fast_gae && git pull && python setup.py build_ext --inplace && cd ../..
cd deps/mettagrid && git pull && python setup.py build_ext --inplace && cd ../..
HYDRA_FULL_ERROR=1 python -m tools.$cmd \
    hardware=pufferbox \
    wandb.enabled=true \
    wandb.track=true $args

