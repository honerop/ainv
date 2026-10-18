use serde_json::Value;

pub fn number(value: &Value, key: &str, default: f64) -> f64 {
    value.get(key).and_then(Value::as_f64).unwrap_or(default)
}

pub fn text<'a>(value: &'a Value, key: &str, default: &'a str) -> &'a str {
    value.get(key).and_then(Value::as_str).unwrap_or(default)
}

fn color(name: &str) -> &str {
    match name {
        "cyan" => "#48dff0", "ice" => "#b9f9ff", "white" => "#f1f7ff",
        "muted" => "#8b9cb2", "navy" => "#101c34", "ink" => "#080d19",
        "panel" => "#17253b", "slate" => "#324059", "blue" => "#6189ff",
        "purple" => "#b592ff", "rose" => "#ff8da9", "red" => "#ff7088",
        "orange" => "#ffbd75", "yellow" => "#ffe18c", "green" => "#7df1bc",
        "black" => "#000000", _ => "#48dff0",
    }
}

fn escape_xml(input: &str) -> String {
    input.replace('&', "&amp;").replace('<', "&lt;")
        .replace('>', "&gt;").replace('"', "&quot;").replace('\'', "&apos;")
}

fn animate(element: &Value, key: &str, progress: f64) -> f64 {
    let base = number(element, key, 0.0);
    let start = element.get("from").map_or(base, |v| number(v, key, base));
    let end = element.get("to").map_or(base, |v| number(v, key, base));
    let p = if text(element, "ease", "linear") == "smooth" {
        progress * progress * (3.0 - 2.0 * progress)
    } else {
        progress
    };
    start + (end - start) * p
}


fn graph_bounds(element: &Value, progress: f64) -> (f64, f64, f64, f64, f64, f64, f64, f64) {
    (
        animate(element, "x", progress),
        animate(element, "y", progress),
        animate(element, "width", progress).max(1.0),
        animate(element, "height", progress).max(1.0),
        number(element, "x_min", -5.0),
        number(element, "x_max", 5.0),
        number(element, "y_min", -3.0),
        number(element, "y_max", 3.0),
    )
}

fn graph_coords(bounds: (f64, f64, f64, f64, f64, f64, f64, f64), x: f64, y: f64) -> (f64, f64) {
    let (left, top, width, height, xmin, xmax, ymin, ymax) = bounds;
    (
        left + ((x - xmin) / (xmax - xmin)) * width,
        top + height - ((y - ymin) / (ymax - ymin)) * height,
    )
}

fn axes(element: &Value, progress: f64) -> String {
    let bounds = graph_bounds(element, progress);
    let (left, top, width, height, xmin, xmax, ymin, ymax) = bounds;
    if xmax <= xmin || ymax <= ymin { return String::new(); }
    let stroke = color(text(element, "stroke", "muted"));
    let mut out = String::from("<g>");
    // Subtle integer grid lines; every label belongs to the coordinate system.
    if xmax - xmin <= 40.0 {
        for i in (xmin.ceil() as i32)..=(xmax.floor() as i32) {
            let (px, _) = graph_coords(bounds, i as f64, 0.0);
            out.push_str(&format!(
                r#"<line x1="{px}" y1="{top}" x2="{px}" y2="{}" stroke="{stroke}" stroke-opacity=".23" stroke-width="1"/>"#,
                top + height
            ));
        }
    }
    if ymax - ymin <= 40.0 {
        for i in (ymin.ceil() as i32)..=(ymax.floor() as i32) {
            let (_, py) = graph_coords(bounds, 0.0, i as f64);
            out.push_str(&format!(
                r#"<line x1="{left}" y1="{py}" x2="{}" y2="{py}" stroke="{stroke}" stroke-opacity=".23" stroke-width="1"/>"#,
                left + width
            ));
        }
    }
    if xmin <= 0.0 && xmax >= 0.0 {
        let (px, _) = graph_coords(bounds, 0.0, 0.0);
        out.push_str(&format!(
            r#"<line x1="{px}" y1="{top}" x2="{px}" y2="{}" stroke="{stroke}" stroke-width="2.5"/>"#,
            top + height
        ));
    }
    if ymin <= 0.0 && ymax >= 0.0 {
        let (_, py) = graph_coords(bounds, 0.0, 0.0);
        out.push_str(&format!(
            r#"<line x1="{left}" y1="{py}" x2="{}" y2="{py}" stroke="{stroke}" stroke-width="2.5"/>"#,
            left + width
        ));
    }
    out.push_str("</g>");
    out
}

fn evaluate_curve(element: &Value, x: f64) -> f64 {
    let a = number(element, "a", 1.0);
    let b = number(element, "b", 0.0);
    let c = number(element, "c", 0.0);
    match text(element, "function", "sin") {
        "sin" => a * (x + b).sin() + c,
        "cos" => a * (x + b).cos() + c,
        "quadratic" | "parabola" => a * x * x + b * x + c,
        "cubic" => a * x * x * x + b * x + c,
        "linear" => a * x + c,
        "exp" => a * (x + b).exp() + c,
        "gaussian" => a * (-(x - b).powi(2)).exp() + c,
        _ => f64::NAN,
    }
}

fn plot(element: &Value, progress: f64) -> String {
    let bounds = graph_bounds(element, progress);
    let (_, _, _, _, xmin, xmax, ymin, ymax) = bounds;
    if xmax <= xmin || ymax <= ymin { return String::new(); }
    let stroke = color(text(element, "stroke", "cyan"));
    let sw = number(element, "stroke_width", 5.0).clamp(0.1, 100.0);
    let opacity = (animate(element, "opacity", progress) / 100.0).clamp(0.0, 1.0);
    let draw_progress = if element.get("draw").and_then(Value::as_bool) == Some(false) {
        1.0
    } else { progress };
    let count = (400.0 * draw_progress).ceil() as usize;
    let mut path = String::new();
    let mut pen_down = false;
    for index in 0..=count {
        let x = xmin + (xmax - xmin) * (index as f64 / 400.0);
        let y = evaluate_curve(element, x);
        if !y.is_finite() || !(ymin..=ymax).contains(&y) {
            pen_down = false;
            continue;
        }
        let (px, py) = graph_coords(bounds, x, y);
        path.push_str(&format!("{} {:.3} {:.3} ", if pen_down { "L" } else { "M" }, px, py));
        pen_down = true;
    }
    format!(
        r#"<path d="{path}" fill="none" stroke="{stroke}" stroke-width="{sw}" opacity="{opacity}" stroke-linecap="round" stroke-linejoin="round"/>"#
    )
}

fn shape(element: &Value, progress: f64) -> String {
    let val = |key: &str| animate(element, key, progress);
    let fill = color(text(element, "fill", "cyan"));
    let stroke = color(text(element, "stroke", "cyan"));
    let opacity = (animate(element, "opacity", progress) / 100.0).clamp(0.0, 1.0);
    let sw = number(element, "stroke_width", 3.0).max(0.0);
    let common = format!(r#"opacity="{opacity:.3}""#);
    match text(element, "kind", "") {
        "axes" => axes(element, progress),
        "plot" => plot(element, progress),
        "rect" => format!(
            r#"<rect x="{}" y="{}" width="{}" height="{}" rx="{}" fill="{fill}" {common}/>"#,
            val("x"), val("y"), val("width").max(0.0), val("height").max(0.0),
            number(element, "radius", 0.0)
        ),
        "circle" => format!(
            r#"<circle cx="{}" cy="{}" r="{}" fill="{fill}" {common}/>"#,
            val("cx"), val("cy"), val("r").max(0.0)
        ),
        "line" | "arrow" => {
            let marker = if text(element, "kind", "") == "arrow" {
                r#"marker-end="url(#ainv-arrow)""#
            } else { "" };
            format!(
                r#"<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" {marker} {common}/>"#,
                val("x1"), val("y1"), val("x2"), val("y2")
            )
        },
        "polyline" => {
            let points = element.get("points").and_then(Value::as_array);
            let points = points.map(|pts| pts.iter().map(|p| {
                format!("{},{}", number(p, "x", 0.0), number(p, "y", 0.0))
            }).collect::<Vec<_>>().join(" ")).unwrap_or_default();
            let offset = 2400.0 * (1.0 - progress);
            format!(
                r#"<polyline points="{points}" fill="none" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="2400" stroke-dashoffset="{offset}" {common}/>"#
            )
        },
        "text" => {
            let weight = match text(element, "weight", "normal") {
                "bold" => "700", "light" => "300", _ => "500"
            };
            let anchor = match text(element, "anchor", "start") {
                "middle" => "middle", "end" => "end", _ => "start"
            };
            let content = escape_xml(text(element, "value", ""));
            format!(
                r#"<text x="{}" y="{}" font-family="DejaVu Sans, Noto Sans, sans-serif" font-size="{}" text-anchor="{anchor}" font-weight="{weight}" fill="{fill}" {common}>{content}</text>"#,
                val("x"), val("y"), number(element, "font_size", 42.0).max(1.0)
            )
        },
        _ => String::new()
    }
}

pub struct Timeline<'a> {
    project: &'a Value,
    pub width: u32,
    pub height: u32,
    pub fps: u32,
    pub frame_count: usize,
    scenes: Vec<(&'a Value, usize, usize)>,
}

impl<'a> Timeline<'a> {
    pub fn new(project: &'a Value) -> Result<Self, String> {
        let w = number(project, "width", 1280.0) as u32;
        let h = number(project, "height", 720.0) as u32;
        let fps = number(project, "fps", 30.0) as u32;
        if !(64..=1920).contains(&w) || !(64..=1080).contains(&h) ||
            w % 2 != 0 || h % 2 != 0 {
            return Err("MP4 width/height must be even and within 64x64..1920x1080".into());
        }
        if !(1..=60).contains(&fps) {
            return Err("fps must be in 1..=60".into());
        }
        let entries = project.get("scenes").and_then(Value::as_array)
            .ok_or("JSON must contain a scenes array")?;
        if entries.is_empty() { return Err("JSON scenes array is empty".into()); }
        let mut cursor = 0_usize;
        let mut scenes = Vec::new();
        for scene in entries {
            let frames = if let Some(n) = scene.get("frames") {
                n.as_u64().ok_or("scene.frames must be a positive integer")? as usize
            } else {
                (number(scene, "duration", 1.0) * f64::from(fps)).round() as usize
            };
            if frames == 0 { return Err("scene length must be positive".into()); }
            if !scene.get("elements").is_some_and(Value::is_array) {
                return Err("each scene must have an elements array".into());
            }
            let end = cursor.checked_add(frames).ok_or("too many frames")?;
            if end > 18000 { return Err("video limited to 18000 frames".into()); }
            scenes.push((scene, cursor, end));
            cursor = end;
        }
        Ok(Self { project, width: w, height: h, fps, frame_count: cursor, scenes })
    }

    pub fn svg_at(&self, index: usize) -> String {
        let &(scene, start, end) = self.scenes.iter()
            .find(|(_, s, e)| index >= *s && index < *e)
            .expect("frame must belong to scene");
        let progress = if end - start <= 1 { 1.0 } else {
            (index - start) as f64 / (end - start - 1) as f64
        };
        let bg = color(text(scene, "background", "ink"));
        let w = self.width;
        let h = self.height;
        let mut svg = format!(
            r##"<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<defs><marker id="ainv-arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 Z" fill="#48dff0"/></marker></defs>
<rect width="{w}" height="{h}" fill="{bg}"/>"##
        );
        if let Some(elements) = scene.get("elements").and_then(Value::as_array) {
            for element in elements {
                svg.push_str(&shape(element, progress));
            }
        }
        svg.push_str("</svg>");
        svg
    }

    pub fn project(&self) -> &Value { self.project }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn plot_draws_more_segments_over_time() {
        let graph: Value = serde_json::json!({
            "kind": "plot", "x": 0, "y": 0, "width": 100, "height": 60,
            "x_min": -2, "x_max": 2, "y_min": -1, "y_max": 4,
            "function": "quadratic"
        });
        let first = plot(&graph, 0.0);
        let last = plot(&graph, 1.0);
        assert!(last.len() > first.len());
        assert!(last.contains("<path"));
    }

    #[test]
    fn axes_render_in_math_coordinates() {
        let axes_json = serde_json::json!({
            "kind": "axes", "x": 100, "y": 100,
            "width": 400, "height": 200,
            "x_min": -2, "x_max": 2, "y_min": -1, "y_max": 1
        });
        let svg = axes(&axes_json, 1.0);
        assert!(svg.contains("<line"));
        assert!(svg.contains("x1=\"300"));
    }

    #[test]
    fn timeline_renders_animation_at_different_times() {
        let json: Value = serde_json::from_str(r#"{"width":128,"height":128,"fps":8,"scenes":[{"frames":3,"elements":[{"kind":"rect","x":10,"y":10,"width":30,"height":20,"from":{"x":0}}]}]}"#).unwrap();
        let tl = Timeline::new(&json).unwrap();
        assert_eq!(tl.frame_count, 3);
        assert_ne!(tl.svg_at(0), tl.svg_at(2));
        assert!(tl.svg_at(1).contains("width=\"30\""));
    }
}
