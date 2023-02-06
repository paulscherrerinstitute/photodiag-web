source /opt/miniconda3/etc/profile.d/conda.sh
conda activate test

python /opt/photodiag_web/photodiag_web/cli.py --ico-path=none --allow-websocket-origin=* --port=5011
