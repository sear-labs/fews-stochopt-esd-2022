#!/usr/bin/env Rscript
# Render farm_report.Rmd once per site.
#
#     Rscript stage2-r/render_reports.R           # every site in config.yaml
#     Rscript stage2-r/render_reports.R EP        # just one
#
# The loop is the whole point. Eleven reports differing in a site name became one
# report and this file, so a change to the aggregation is made once.
#
# Called by `python scripts/run_all.py --reports`, and runnable on its own.

suppressPackageStartupMessages({
  library(rmarkdown)
})

root <- normalizePath(file.path(dirname(sub("^--file=", "", grep("^--file=",
  commandArgs(trailingOnly = FALSE), value = TRUE)[1])), ".."), mustWork = TRUE)

# Both parameterised documents, each rendered once per site. There is no third:
# the eleven site-specific reports these replaced are under superseded/.
documents <- c(
  farm_report  = file.path(root, "stage2-r", "farm_report.Rmd"),
  markov_chain = file.path(root, "stage2-r", "markov_chain.Rmd")
)
stopifnot(all(file.exists(documents)))

# The site list and its labels come from config.yaml, so this script holds no
# copy of them. Parsing the two lines needed avoids a yaml package dependency
# for a file this simple, and fails loudly rather than guessing.
read_sites <- function(path) {
  lines <- readLines(path, warn = FALSE)
  start <- grep("^sites:\\s*$", lines)
  if (length(start) != 1L) stop("config.yaml has no unique `sites:` block")
  rest <- lines[(start + 1):length(lines)]
  end <- grep("^[a-zA-Z]", rest)
  block <- if (length(end)) rest[seq_len(end[1] - 1)] else rest

  keys <- grep("^  [A-Za-z0-9_]+:\\s*$", block)
  if (!length(keys)) stop("config.yaml `sites:` block lists no sites")
  out <- list()
  for (i in seq_along(keys)) {
    name <- trimws(sub(":", "", block[keys[i]]))
    upto <- if (i < length(keys)) keys[i + 1] - 1 else length(block)
    label_line <- grep("^\\s+label:", block[keys[i]:upto], value = TRUE)
    if (!length(label_line)) stop("site ", name, " has no label in config.yaml")
    out[[name]] <- trimws(sub("^\\s+label:\\s*", "", label_line[1]))
  }
  out
}

sites <- read_sites(file.path(root, "config.yaml"))

requested <- commandArgs(trailingOnly = TRUE)
if (length(requested)) {
  unknown <- setdiff(requested, names(sites))
  if (length(unknown)) {
    stop("unknown site(s): ", paste(unknown, collapse = ", "),
         ". config.yaml defines: ", paste(names(sites), collapse = ", "))
  }
  sites <- sites[requested]
}

stopifnot(length(sites) > 0)

out_dir <- file.path(root, "results", "reports")
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

rendered <- 0
for (site in names(sites)) {
  label <- sites[[site]]
  for (name in names(documents)) {
    cat(sprintf("rendering %-13s %s (%s)\n", name, site, label))
    render(
      documents[[name]],
      params = list(site = site, label = label, root = root),
      output_file = sprintf("%s_%s.html", name, site),
      output_dir = out_dir,
      envir = new.env(),
      quiet = TRUE
    )
    rendered <- rendered + 1
  }
}

stopifnot(rendered == length(sites) * length(documents))
cat(sprintf("wrote %d report(s) to %s\n", rendered, out_dir))
