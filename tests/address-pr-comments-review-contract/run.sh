#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
MANIFEST="$SCRIPT_DIR/manifest.tsv"
FIXTURE_DIR="$SCRIPT_DIR/fixtures"
CHECKER="$SCRIPT_DIR/../../scripts/check-address-pr-comments-review-contract.sh"
CROSS_REF_CHECKER="$SCRIPT_DIR/../../scripts/check-cross-refs.sh"

EXPLICIT_ROOT="${1:-}"

total=0
passed=0
failed=0

# Read manifest and process each row using perl for proper TSV parsing
perl -e '
    use strict;
    use warnings;
    use File::Path qw(make_path remove_tree);
    use File::Copy qw(copy);
    use Digest::SHA qw(sha256_hex);
    use MIME::Base64;

    my $manifest_file = $ARGV[0];
    my $fixture_dir   = $ARGV[1];
    my $checker       = $ARGV[2];
    my $explicit_root = $ARGV[3] || "";
    my $script_dir    = $ARGV[4];

    my $total  = 0;
    my $passed = 0;
    my $failed = 0;

    open(my $mf, "<", $manifest_file) or die "open manifest: $!";

    while (<$mf>) {
        chomp;
        next if /^#/;
        next if /^\s*$/;
        next if /^case_id	/;

        my @fields = split /	/;
        die "bad row: $_" unless @fields >= 8;
        my ($case_id, $fixture, $mut_path, $mut_op, $from_b64, $to_b64, $expected_exit, $expected_diag) = @fields;

        my $fixture_file = "$fixture_dir/$fixture";
        unless (-f $fixture_file) {
            print "  SKIP: fixture not found: $fixture\n";
            $total++; $failed++;
            next;
        }

        # Create temp dir
        my $tmpdir = "/tmp/apr-contract-test-" . int(rand(999999));
        make_path($tmpdir);

        # Init git repo
        system("cd $tmpdir && git init -q && git config user.email test\@test && git config user.name test") == 0 or die "git init";

        # Create rubric.md only if fixture did not provide one
        unless (-f "$tmpdir/tests/address-pr-comments-review-eval/rubric.md") {
            make_path("$tmpdir/tests/address-pr-comments-review-eval");
            open(my $rb, ">", "$tmpdir/tests/address-pr-comments-review-eval/rubric.md") or die;
            print $rb "# Rubric\\n<!-- rubric-v1:start -->\\nScoring criteria.\\n<!-- rubric-v1:end -->\\n";
            close $rb;
        }

        # Materialize fixture
        open(my $ff, "<", $fixture_file) or die "open fixture: $!";
        my $fheader = <$ff>;
        die "bad fixture" unless $fheader =~ /^# fixture-v1/;

        while (<$ff>) {
            chomp;
            next if /^\s*$/;
            my ($path, $type, $payload, $expected_sha) = split /	/;
            my $full_path = "$tmpdir/$path";
            my $dir = $full_path;
            $dir =~ s{/[^/]*$}{};
            make_path($dir) unless -d $dir;

            if ($type eq "file") {
                my $content = MIME::Base64::decode_base64($payload);
                open(my $out, ">", $full_path) or die "write $full_path: $!";
                print $out $content;
                close $out;
            } elsif ($type eq "symlink") {
                my $target = MIME::Base64::decode_base64($payload);
                symlink($target, $full_path) or warn "symlink $full_path -> $target";
            }
        }
        close $ff;

        # Apply mutation
        if ($mut_op && $mut_path && $from_b64 && $to_b64) {
            my $target = "$tmpdir/$mut_path";
            if (-f $target) {
                my $from = MIME::Base64::decode_base64($from_b64);
                my $to   = MIME::Base64::decode_base64($to_b64);

                open(my $fh, "<", $target) or die "open: $!";
                my $content = do { local $/; <$fh> };
                close $fh;

                if ($mut_op eq "replace") {
                    my $pos = index($content, $from);
                    if ($pos >= 0) {
                        substr($content, $pos, length($from)) = $to;
                    } else {
                        warn "from string not found in $target";
                    }
                }

                open(my $out, ">", $target) or die "write: $!";
                print $out $content;
                close $out;
            }
        }

        # Create a fake git commit so git rev-parse works
        system("cd $tmpdir && git add -A && git commit -q -m init") == 0 or warn "git commit";

        # Invoke checker
        my $checker_root = $explicit_root || $tmpdir;
        my $stderr_file = "$tmpdir/.stderr";
        my $actual_exit = system("bash \"$checker\" \"$checker_root\" >/dev/null 2>\"$stderr_file\"") >> 8;

        my $actual_diag = "";
        if (-s $stderr_file) {
            open(my $se, "<", $stderr_file) or die;
            my $stderr = do { local $/; <$se> };
            close $se;
            ($actual_diag) = ($stderr =~ /(APR\d+)/);
            $actual_diag ||= "";
        }

        # Compare
        my $ok = 1;
        $ok = 0 unless $actual_exit == $expected_exit;

        if ($expected_diag eq "-") {
            $ok = 0 if $actual_diag ne "";
        } else {
            $ok = 0 unless $actual_diag eq $expected_diag;
        }

        $total++;
        if ($ok) {
            $passed++;
            print "  OK: $case_id\n";
        } else {
            $failed++;
            print "  FAIL: $case_id (expected exit=$expected_exit diag=$expected_diag, got exit=$actual_exit diag=$actual_diag)\n";
            if (-s $stderr_file) {
                open(my $se, "<", $stderr_file);
                while (<$se>) { print "    $_"; }
                close $se;
            }
        }

        remove_tree($tmpdir);
    }
    close $mf;

    print "\ntotal=$total passed=$passed failed=$failed\n";
    exit($failed > 0 ? 1 : 0);
' "$MANIFEST" "$FIXTURE_DIR" "$CHECKER" "$EXPLICIT_ROOT" "$SCRIPT_DIR"
