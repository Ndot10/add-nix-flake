use std::{
    fs::{
        self,
    },
    path::PathBuf,
};

use annotate_snippets::{
    Level,
    Renderer,
    Snippet,
};
use colored::Colorize;
use logos::Span;

use super::{
    diagnostic_kind::DiagnosticKind,
    Diagnostic,
};
use crate::{
    ast::Project,
    standard_library::StandardLibrary,
    translation_unit::{
        Owner,
        TranslationUnit,
    },
};

pub struct SpriteDiagnostics {
    sprite_name: String,
    pub translation_unit: TranslationUnit,
    pub diagnostics: Vec<Diagnostic>,
}

impl SpriteDiagnostics {
    pub fn new(path: PathBuf, stdlib: &StandardLibrary) -> Self {
        let sprite_name = path.file_stem().unwrap().to_str().unwrap().to_string();
        let mut translation_unit = TranslationUnit::new(path);
        let mut diagnostics = vec![];
        if let Err(diagnostic) = translation_unit.pre_process(stdlib) {
            diagnostics.extend(diagnostic);
        }
        Self {
            sprite_name,
            translation_unit,
            diagnostics,
        }
    }

    pub fn report(&mut self, kind: DiagnosticKind, span: &Span) {
        self.diagnostics.push(Diagnostic {
            kind,
            span: span.clone(),
        });
    }

    pub fn eprint(&self, renderer: &Renderer, project: &Project) {
        let sprite = match self.sprite_name.as_str() {
            "stage" => &project.stage,
            name => &project.sprites[name],
        };
        for diagnostic in &self.diagnostics {
            let level: Level = (&diagnostic.kind).into();
            let title = diagnostic.kind.to_string(sprite);
            let help = diagnostic.kind.help();
            let help = help.as_ref();
            let (start, include) = self
                .translation_unit
                .translate_position(diagnostic.span.start);
            if level != Level::Error && !matches!(include.owner, Owner::Local) {
                continue;
            }
            if diagnostic.kind.should_be_suppressed() {
                continue;
            }
            // TODO: memoize this using a memoization crate.
            let text = fs::read_to_string(&include.path).unwrap();
            let include_path = include.path.to_str().unwrap();
            if diagnostic.span.start == 0 && diagnostic.span.end == 0 {
                let mut message = level
                    .title(&title)
                    .snippet(Snippet::source(&text).origin(include_path).fold(true));
                if let Some(help) = help {
                    message = message.footer(Level::Help.title(help));
                }
                eprintln!("{}", renderer.render(message));
            } else {
                let (end, _) = self
                    .translation_unit
                    .translate_position(diagnostic.span.end - 1);
                let end = end + 1;
                let mut message = level.title(&title).snippet(
                    Snippet::source(&text)
                        .origin(include_path)
                        .fold(true)
                        .annotation(level.span(start..end)),
                );
                if let Some(help) = help {
                    message = message.footer(Level::Help.title(help));
                }
                eprintln!("{}", renderer.render(message));
            }
            if let DiagnosticKind::CommandFailed { stderr } = &diagnostic.kind {
                eprintln!("{}:", "stderr".red().bold());
                for line in stderr.split(|&b| b == b'\n') {
                    eprintln!("    {}", std::str::from_utf8(line).unwrap().red());
                }
            }
        }
    }
}
