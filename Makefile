PYTHON ?= python3
PREFIX ?= /usr/local
BINARY := portscanner
SOURCES := $(shell find src -name '*.py')

.PHONY: all build run test install uninstall clean

all: build

build: $(BINARY)

$(BINARY): $(SOURCES)
	find src -name __pycache__ -type d -prune -exec rm -rf {} +
	$(PYTHON) -m zipapp src -m "portscanner.app:cli" -p "/usr/bin/env python3" -o $(BINARY)
	chmod 755 $(BINARY)

run:
	PYTHONPATH=src $(PYTHON) -m portscanner

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

install: $(BINARY)
	install -d "$(DESTDIR)$(PREFIX)/bin"
	install -m 755 $(BINARY) "$(DESTDIR)$(PREFIX)/bin/$(BINARY)"

uninstall:
	rm -f "$(DESTDIR)$(PREFIX)/bin/$(BINARY)"

clean:
	rm -f $(BINARY)
