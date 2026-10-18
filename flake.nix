{
  description = "AinV: narrated mathematical animations with Nix-native MP4 export";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      eachSystem = nixpkgs.lib.genAttrs systems;
      pkgsFor = system: import nixpkgs { inherit system; };
      nativeFor = system:
        let pkgs = pkgsFor system;
        in pkgs.rustPlatform.buildRustPackage {
          pname = "ainv-native";
          version = "0.1.0";
          src = ./.;
          cargoRoot = "native";
          buildAndTestSubdir = "native";
          cargoLock.lockFile = ./native/Cargo.lock;
          nativeBuildInputs = [ pkgs.nasm pkgs.pkg-config ];
          buildInputs = [ pkgs.fontconfig ];
          doCheck = true;
          meta = {
            description = "FFmpeg-free H.264 MP4 renderer for AinV JSON scenes";
            mainProgram = "ainv-native";
            platforms = systems;
          };
        };
      appFor = system:
        let
          pkgs = pkgsFor system;
          native = nativeFor system;
          python = pkgs.python3.withPackages (ps: [ ps.edge-tts ]);
        in pkgs.writeShellScriptBin "ainv" ''
          set -euo pipefail
          export AINV_FONT_DIR="${pkgs.dejavu_fonts}/share/fonts/truetype"
          export AINV_NATIVE="${native}/bin/ainv-native"
          export AINV_DEFAULT_SPEC="${./examples/math-explainer.json}"
          export AINV_EDGE_TTS="${python}/bin/edge-tts"
          export AINV_FFMPEG="${pkgs.ffmpeg}/bin/ffmpeg"
          export AINV_FFPROBE="${pkgs.ffmpeg}/bin/ffprobe"
          exec "${python}/bin/python3" "${./pipeline.py}" "$@"
        '';
    in {
      packages = eachSystem (system: {
        native = nativeFor system;
        default = appFor system;
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
          python = pkgs.python3.withPackages (ps: [ ps.edge-tts ]);
        in {
          native = nativeFor system;
          pipeline = pkgs.runCommand "ainv-pipeline-tests" {
            nativeBuildInputs = [ python pkgs.ffmpeg ];
          } ''
            export HOME="$TMPDIR"
            cd ${./.}
            python3 -m unittest discover -s tests -p test_pipeline.py -v
            touch "$out"
          '';
        });

      devShells = eachSystem (system:
        let
          pkgs = pkgsFor system;
          python = pkgs.python3.withPackages (ps: [ ps.edge-tts ]);
        in {
          default = pkgs.mkShell {
            packages = [
              python pkgs.ffmpeg pkgs.rustc pkgs.cargo
              pkgs.gcc pkgs.nasm pkgs.pkg-config pkgs.fontconfig
            ];
            AINV_FONT_DIR = "${pkgs.dejavu_fonts}/share/fonts/truetype";
          };
        });
    };
}
