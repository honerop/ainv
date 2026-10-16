{
  description = "AinV: JSON motion graphics rendered as real H.264 MP4 video";

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
        in pkgs.writeShellScriptBin "ainv" ''
          set -euo pipefail
          export AINV_FONT_DIR="${pkgs.dejavu_fonts}/share/fonts/truetype"
          if [ "$#" -eq 0 ]; then
            exec "${native}/bin/ainv-native" "${./examples/showcase.json}" "showcase.mp4"
          elif [ "$#" -eq 1 ]; then
            exec "${native}/bin/ainv-native" "$1" "output.mp4"
          elif [ "$#" -eq 2 ]; then
            exec "${native}/bin/ainv-native" "$1" "$2"
          else
            echo "Usage: nix run github:honerop/ainv [-- INPUT.json [OUTPUT.mp4]]" >&2
            exit 2
          fi
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

      checks = eachSystem (system: {
        native = nativeFor system;
      });
    };
}
