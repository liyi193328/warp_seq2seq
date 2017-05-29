#! /bin/bash/ env

DATA_DIR=${data_dir:-"/home/bigdata/active_project/test_seq2seq_py2/yard_seq2seq/data/q2q_12w_cancel_dup"}
MODEL_NAME=${model_name:-"add_residual_connections"}
CONFIG_DIR=${conf_dir:-"../example_configs/q2q_12w"}
SEQ2SEQ_PROJECT=${seq2seq_project:-"/home/active_project/seq2seq"}
export CUDA_VISIBLE_DEVICES=""; python $SEQ2SEQ_PROJECT/bin/train.py --config_path="../example_configs/q2q_12w/nmt_small.yml, ../example_configs/q2q_12w/train_seq2seq.yml, ../example_configs/q2q_12w/text_metrics_bpe.yml" --ps_hosts="localhost:2222" --worker_hosts="localhost:2223,localhost:2224,localhost:2225" --job_name="ps" --task_index=0 --cloud=True --schedule="default" --output_dir="${DATA_DIR}/model/$MODEL_NAME" --gpu_memory_fraction=1 --eval_every_n_steps=8000 --train_steps=200000 --batch_size=64 --max_--save_checkpoints_secs=1200 --keep_checkpoint_max=10 clear_output_dir=False > ${DATA_DIR}/ps_${MODEL_NAME}.log 2>&1 &
export CUDA_VISIBLE_DEVICES="0";python $SEQ2SEQ_PROJECT/bin/train.py --config_path="../example_configs/q2q_12w/nmt_small.yml, ../example_configs/q2q_12w/train_seq2seq.yml, ../example_configs/q2q_12w/text_metrics_bpe.yml" --ps_hosts="localhost:2222" --worker_hosts="localhost:2223,localhost:2224,localhost:2225" --job_name="worker" --task_index=0 --cloud=True --schedule="train" --output_dir="${DATA_DIR}/model/$MODEL_NAME" --gpu_memory_fraction=0.5 --eval_every_n_steps=8000 --train_steps=200000 --batch_size=64 --max_--save_checkpoints_secs=1200 --keep_checkpoint_max=10 --clear_output_dir=False > ${DATA_DIR}/worker0_${MODEL_NAME}.log 2>&1 &
export CUDA_VISIBLE_DEVICES="0";python $SEQ2SEQ_PROJECT/bin/train.py --config_path="../example_configs/q2q_12w/nmt_small.yml, ../example_configs/q2q_12w/train_seq2seq.yml, ../example_configs/q2q_12w/text_metrics_bpe.yml" --ps_hosts="localhost:2222" --worker_hosts="localhost:2223,localhost:2224,localhost:2225" --job_name="worker" --task_index=1 --cloud=True --schedule="train" --output_dir="${DATA_DIR}/model/$MODEL_NAME" --gpu_memory_fraction=0.5 --eval_every_n_steps=8000 --train_steps=200000 --batch_size=64 --max_--save_checkpoints_secs=1200 --keep_checkpoint_max=10 --clear_output_dir=False > ${DATA_DIR}/worker1_${MODEL_NAME}.log 2>&1 &
export CUDA_VISIBLE_DEVICES=""; python $SEQ2SEQ_PROJECT/bin/train.py --config_path="../example_configs/q2q_12w/nmt_small.yml, ../example_configs/q2q_12w/train_seq2seq.yml, ../example_configs/q2q_12w/text_metrics_bpe.yml" --ps_hosts="localhost:2222" --worker_hosts="localhost:2223,localhost:2224,localhost:2225" --job_name="worker" --task_index=2 --cloud=True --schedule="continuous_eval" --output_dir="${DATA_DIR}/model/$MODEL_NAME" --gpu_memory_fraction=1 --eval_every_n_steps=8000 --train_steps=200000 --batch_size=64 --max_--save_checkpoints_secs=1200 --keep_checkpoint_max=10 --clear_output_dir=False > ${DATA_DIR}/worker2_${MODEL_NAME}.log 2>&1 &