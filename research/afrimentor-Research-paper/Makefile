.PHONY: all clean

MAIN = main

all: $(MAIN).pdf

$(MAIN).pdf: $(MAIN).tex sections/*.tex refs.bib
	pdflatex -interaction=nonstopmode $(MAIN).tex
	bibtex $(MAIN)
	pdflatex -interaction=nonstopmode $(MAIN).tex
	pdflatex -interaction=nonstopmode $(MAIN).tex

clean:
	rm -f *.aux *.bbl *.blg *.log *.out *.toc $(MAIN).pdf
