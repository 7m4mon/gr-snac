# Source this file from Ubuntu / WSL: source tools/activate-wsl.sh
_gr_snac_env="$HOME/.venvs/gr-snac"
if [ ! -f "$_gr_snac_env/bin/activate" ]; then
    printf '%s\n' "Missing environment: $_gr_snac_env" >&2
    return 1
fi
source "$_gr_snac_env/bin/activate"
_gr_snac_python="$_gr_snac_env/lib/python$(python -c 'import sys; print("%d.%d" % sys.version_info[:2])')/site-packages"
export PYTHONPATH="$_gr_snac_python${PYTHONPATH:+:$PYTHONPATH}"
export GRC_BLOCKS_PATH="$_gr_snac_env/share/gnuradio/grc/blocks${GRC_BLOCKS_PATH:+:$GRC_BLOCKS_PATH}"
unset _gr_snac_env _gr_snac_python
