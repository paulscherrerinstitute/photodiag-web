source /opt/miniconda3/etc/profile.d/conda.sh
conda activate prod

photodiag_web --ico-path=none --allow-websocket-origin=* --port=5010
