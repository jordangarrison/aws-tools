{
  description = "AWS Tools – Collection of Python CLI utilities for AWS";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        py = pkgs.python313;
        pyPkgs = py.pkgs;

        # Common build inputs for Python applications
        commonBuildInputs = [
          pyPkgs.pdm-backend
          pyPkgs.setuptools
          pyPkgs.pip
          pyPkgs.wheel
        ];

        # Build the AWS Tools package
        aws-tools = pyPkgs.buildPythonApplication {
          pname = "aws-tools";
          version = "0.1.0";
          src = self;
          format = "pyproject";

          nativeBuildInputs = commonBuildInputs;
          propagatedBuildInputs = [
            pyPkgs.boto3
            pyPkgs.colorama
          ];

          # Package the aws_tools folder correctly
          preBuild = ''
            export PYTHONPATH=$PYTHONPATH:$src/src
          '';

          # `doCheck = true` once you add unit tests
        };

        # Create a wrapper Python environment with all dependencies
        aws-tools-env = py.withPackages (ps: [ aws-tools ps.boto3 ps.colorama ]);

        # ── Individual tool packages as wrappers ────────────────────────────
        dns-upload = pkgs.writeShellScriptBin "dns-upload" ''
          ${aws-tools-env}/bin/python -m aws_tools.dns_upload "$@"
        '';

        reboot-ec2 = pkgs.writeShellScriptBin "reboot-ec2" ''
          ${aws-tools-env}/bin/python -m aws_tools.reboot_ec2 "$@"
        '';

        # Meta-package that includes all tools
        aws-tools-collection = pkgs.symlinkJoin {
          name = "aws-tools-collection";
          paths = [ dns-upload reboot-ec2 ];
          meta = {
            description = "Collection of AWS utility tools";
            mainProgram = "dns-upload";
          };
        };
      in
      {
        # ── Packages ────────────────────────────────────────────────────────────
        packages = {
          default = aws-tools-collection;
          aws-tools = aws-tools;
          dns-upload = dns-upload;
          reboot-ec2 = reboot-ec2;
          aws-tools-collection = aws-tools-collection;
        };

        # ── Apps (directly runnable) ────────────────────────────────────────────
        apps = {
          default = flake-utils.lib.mkApp {
            drv = dns-upload;
            name = "dns-upload";
          };

          dns-upload = flake-utils.lib.mkApp {
            drv = dns-upload;
            name = "dns-upload";
          };

          reboot-ec2 = flake-utils.lib.mkApp {
            drv = reboot-ec2;
            name = "reboot-ec2";
          };
        };

        # ── Development shell ────────────────────────────────────────────────────
        devShells.default = pkgs.mkShell {
          packages = [
            py
            pkgs.pdm
            pyPkgs.ipython
            pkgs.nixpkgs-fmt
            # Build dependencies
            pyPkgs.setuptools
            pyPkgs.pip
            pyPkgs.wheel
            # Runtime dependencies
            pyPkgs.boto3
            pyPkgs.colorama
          ];
          shellHook = ''
            export PYTHONPATH="$PWD/src:$PYTHONPATH"
            export PDM_IGNORE_SAVED_PYTHON=1
            export PDM_PYTHON="${py}/bin/python"
            echo "🔧 AWS Tools Dev Shell"
            echo "🔧 Python: ${py}/bin/python"
            echo "🔧 Available tools:"
            echo "  - dns-upload: Route53 DNS Records Bulk Upload Utility"
            echo "  - reboot-ec2: EC2 Instance Reboot Utility"
            echo ""
            echo "To run a tool: nix run .#[tool-name]"
            echo "To install a tool: nix profile install .#[tool-name]"
          '';
        };
      });
}
