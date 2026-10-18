{
  description = "AinV: Ain-authored general video timeline and MP4 media compositor";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.ain.url = "github:honerop/ain";

  outputs = { self, nixpkgs, ain }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      eachSystem = nixpkgs.lib.genAttrs systems;
      pkgsFor = system: import nixpkgs { inherit system; };

      compilerFor = system:
        let pkgs = pkgsFor system;
        in pkgs.stdenv.mkDerivation {
          pname = "ainc";
          version = "0.3.0";
          src = ain;
          nativeBuildInputs = [ pkgs.rustc ];
          dontConfigure = true;
          buildPhase = ''
            runHook preBuild
            rustc --edition=2021 --crate-name ain_compiler --crate-type rlib -O src/lib.rs -o libain_compiler.rlib
            rustc --edition=2021 -O src/main.rs --extern ain_compiler=libain_compiler.rlib -L dependency=. -o ainc
            runHook postBuild
          '';
          installPhase = ''
            mkdir -p "$out/bin"
            cp ainc "$out/bin/ainc"
          '';
        };

      directorFor = system:
        let
          pkgs = pkgsFor system;
          compiler = compilerFor system;
        in pkgs.stdenv.mkDerivation {
          pname = "ainv-director";
          version = "0.2.0";
          src = ./.;
          dontConfigure = true;
          nativeBuildInputs = [ compiler pkgs.rustc ];
          buildPhase = ''
            runHook preBuild
            ${compiler}/bin/ainc check director.ain
            ${compiler}/bin/ainc build director.ain -o ainv
            runHook postBuild
          '';
          installPhase = ''
            mkdir -p "$out/bin"
            cp ainv "$out/bin/ainv-director"
          '';
          meta.mainProgram = "ainv-director";
        };

      appFor = system:
        let
          pkgs = pkgsFor system;
          director = directorFor system;
          python = pkgs.python3.withPackages (ps: [ ps.edge-tts ]);
          fonts = pkgs.makeFontsConf { fontDirectories = [ pkgs.dejavu_fonts ]; };
        in pkgs.writeShellScriptBin "ainv" ''
          set -euo pipefail
          export AINV_DEFAULT_SPEC="${./examples/general-showcase.json}"
          export AINV_EDGE_TTS="${python}/bin/edge-tts"
          export AINV_ESPEAK="${pkgs.espeak-ng}/bin/espeak-ng"
          export AINV_FFPROBE="${pkgs.ffmpeg}/bin/ffprobe"
          export AINV_FFMPEG="${pkgs.ffmpeg}/bin/ffmpeg"
          export AINV_RSVG="${pkgs.librsvg}/bin/rsvg-convert"
          export AINV_DIRNAME="${pkgs.coreutils}/bin/dirname"
          export FONTCONFIG_FILE="${fonts}"
          export AIN_PROCESS_TIMEOUT_MS=1800000
          export AINV_WORK="$(mktemp -d)"
          trap 'rm -rf "$AINV_WORK"' EXIT
          "${director}/bin/ainv-director" "$@"
        '';
    in {
      packages = eachSystem (system: {
        default = appFor system;
        ainv = directorFor system;
        compiler = compilerFor system;
      });

      apps = eachSystem (system: {
        default = {
          type = "app";
          program = "${appFor system}/bin/ainv";
        };
      });

      checks = eachSystem (system:
        let
          pkgs = pkgsFor system;
          director = directorFor system;
          app = appFor system;
        in {
          ain-director = director;
          smoke = pkgs.runCommand "ainv-smoke" { } ''
            mkdir -p "$out"
            cd "$out"
            "${app}/bin/ainv" "${./examples/ain-smoke.json}" "smoke.mp4"
            test -s smoke.mp4
            test -s smoke.srt
            ${pkgs.ffmpeg}/bin/ffprobe -v error -show_entries stream=codec_name,width,height -of json smoke.mp4 > info.json
            grep -q h264 info.json
          '';
        });

      devShells = eachSystem (system:
        let
          pkgs = pkgsFor system;
          python = pkgs.python3.withPackages (ps: [ ps.edge-tts ]);
        in {
          default = pkgs.mkShell {
            packages = [
              (compilerFor system)
              python pkgs.ffmpeg pkgs.librsvg pkgs.rustc
              pkgs.cargo pkgs.pkg-config pkgs.fontconfig
            ];
          };
        });
    };
}
