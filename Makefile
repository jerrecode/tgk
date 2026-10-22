CC ?= cc
CFLAGS ?= -O3 -std=c11 -fPIC -Wall -Wextra -Werror
.PHONY: build test check clean
build:
	$(CC) $(CFLAGS) -shared -o tgk/libtgk.so tgk/native/tgk_canvas.c -lm
test: build
	python -m unittest discover -s tests -v
check: test
	python -m compileall -q tgk tests examples
clean:
	rm -f tgk/libtgk.so
