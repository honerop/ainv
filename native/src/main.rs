mod scene;

use std::{env, error::Error, fs, fs::File, path::Path, io::BufReader};
use mp4::{AvcConfig, Bytes, Mp4Config, Mp4Sample, Mp4Writer, TrackConfig};
use openh264::{encoder::Encoder, formats::{RgbSliceU8, YUVBuffer}};
use serde_json::Value;

type Result<T> = std::result::Result<T, Box<dyn Error>>;

fn rgb_for_svg(svg: &str, width: u32, height: u32, options: &resvg::usvg::Options<'_>) -> Result<Vec<u8>> {
    let tree = resvg::usvg::Tree::from_str(svg, options)?;
    let mut pixmap = resvg::tiny_skia::Pixmap::new(width, height)
        .ok_or("Could not allocate raster buffer")?;
    resvg::render(&tree, resvg::tiny_skia::Transform::identity(), &mut pixmap.as_mut());
    let mut rgb = Vec::with_capacity((width as usize) * (height as usize) * 3);
    for px in pixmap.data().chunks_exact(4) {
        rgb.extend_from_slice(&px[..3]);
    }
    Ok(rgb)
}

// The H.264 encoder returns Annex B NALs, but an MP4 avc1 sample
// contains length-prefixed NAL units. Parameter sets live in avcC.
fn avcc_packet(raw: &[u8], sps: &mut Vec<u8>, pps: &mut Vec<u8>) -> Result<(Vec<u8>, bool)> {
    let mut payload = Vec::new();
    let mut sync = false;
    for packet in openh264::nal_units(raw) {
        let nal = if packet.starts_with(&[0, 0, 0, 1]) {
            &packet[4..]
        } else if packet.starts_with(&[0, 0, 1]) {
            &packet[3..]
        } else {
            return Err("encoder produced NAL without start code".into());
        };
        if nal.is_empty() { continue; }
        match nal[0] & 0x1f {
            7 => { *sps = nal.to_vec(); continue; }
            8 => { *pps = nal.to_vec(); continue; }
            5 => sync = true,
            _ => {}
        }
        payload.extend_from_slice(&u32::try_from(nal.len())?.to_be_bytes());
        payload.extend_from_slice(nal);
    }
    Ok((payload, sync))
}

fn export(spec: &Path, output: &Path) -> Result<()> {
    let doc: Value = serde_json::from_slice(&fs::read(spec)?)?;
    let timeline = scene::Timeline::new(&doc)?;
    let width = timeline.width;
    let height = timeline.height;
    let fps = timeline.fps;
    eprintln!("ainv: {}x{} @ {} fps, {} frames", width, height, fps, timeline.frame_count);

    let mut options = resvg::usvg::Options::default();
    options.fontdb_mut().load_system_fonts();

    let mut encoder = Encoder::new()?;
    let config = Mp4Config {
        major_brand: "isom".parse()?,
        minor_version: 512,
        compatible_brands: ["isom", "iso2", "avc1", "mp41"]
            .iter().map(|s| s.parse()).collect::<std::result::Result<Vec<_>, _>>()?,
        timescale: fps,
    };

    let mut writer = Mp4Writer::write_start(File::create(output)?, &config)?;
    let mut track_created = false;
    let mut sps = Vec::new();
    let mut pps = Vec::new();
    for index in 0..timeline.frame_count {
        let svg = timeline.svg_at(index);
        let rgb = rgb_for_svg(&svg, width, height, &options)?;
        let input = RgbSliceU8::new(&rgb, (width as usize, height as usize));
        let yuv = YUVBuffer::from_rgb_source(input);
        let encoded = encoder.encode(&yuv)?;
        let (sample_bytes, is_sync) = avcc_packet(&encoded.to_vec(), &mut sps, &mut pps)?;
        if !track_created {
            if sps.is_empty() || pps.is_empty() {
                return Err("H.264 encoder did not provide SPS and PPS".into());
            }
            let track = TrackConfig {
                timescale: fps,
                ..AvcConfig {
                    width: u16::try_from(width)?,
                    height: u16::try_from(height)?,
                    seq_param_set: sps.clone(),
                    pic_param_set: pps.clone(),
                }.into()
            };
            writer.add_track(&track)?;
            track_created = true;
        }
        if sample_bytes.is_empty() {
            return Err(format!("encoder produced empty sample at frame {index}").into());
        }
        let sample = Mp4Sample {
            start_time: index as u64,
            duration: 1,
            rendering_offset: 0,
            is_sync,
            bytes: Bytes::from(sample_bytes),
        };
        writer.write_sample(1, &sample)?;
        if index % (fps as usize) == 0 {
            eprintln!("ainv: rendered {}/{} frames", index + 1, timeline.frame_count);
        }
    }
    writer.write_end()?;
    let size = fs::metadata(output)?.len();
    eprintln!("ainv: finished {} ({size} bytes)", output.display());

    let f = File::open(output)?;
    let reader = Mp4Reader::read_header(BufReader::new(f), size)?;
    if reader.sample_count(1)? != timeline.frame_count as u32 {
        return Err("MP4 did not contain the expected number of samples".into());
    }
    println!("MP4 OK: {} frames, {}x{} H.264 video: {}", timeline.frame_count, width, height, output.display());
    Ok(())
}

use mp4::Mp4Reader;
fn main() {
    let args = env::args().collect::<Vec<_>>();
    if args.len() != 3 {
        eprintln!("Usage: ainv-native INPUT.json OUTPUT.mp4");
        std::process::exit(2);
    }
    let output = Path::new(&args[2]);
    if let Err(error) = export(Path::new(&args[1]), output) {
        eprintln!("MP4 export failed: {error}");
        let _ = fs::remove_file(output);
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn annex_b_parameter_sets_become_mp4_avcc() {
        let bytes = [
            0,0,0,1,0x67,0x42,0xe0,0x1e,
            0,0,0,1,0x68,0xce,0x06,
            0,0,1,0x65,0x88,0x84,
        ];
        let (mut sps, mut pps)=(Vec::new(),Vec::new());
        let (out,key) = avcc_packet(&bytes,&mut sps,&mut pps).unwrap();
        assert!(key);
        assert_eq!(sps[0],0x67);
        assert_eq!(pps[0],0x68);
        assert_eq!(out,vec![0,0,0,3,0x65,0x88,0x84]);
    }
}
