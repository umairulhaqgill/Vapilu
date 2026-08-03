ince launchctl setenv doesn't persist across a reboot, that setting reset — that's almost certainly why. On the Mac:


launchctl setenv OLLAMA_HOST "0.0.0.0"
open -a Ollama
(If you normally run it via ollama serve in a terminal instead of the app, use export OLLAMA_HOST=0.0.0.0 in that terminal before running ollama serve.)

Let me know once it's back 