function capture_kernels(toolboxRoot, outputDirectory)
% Portable reference capture. Run beside the frozen original toolbox.
% Does not modify source files or require participant recordings.
% MATLAB/SPM are development reference tools only, never Python dependencies.
rootFile = java.io.File(toolboxRoot);
toolboxRoot = char(rootFile.getCanonicalPath());
assert(~exist(outputDirectory, 'file'), 'Output directory already exists');
mkdir(outputDirectory);
oldPath = path;
restorePath = onCleanup(@() path(oldPath)); %#ok<NASGU>
addpath(genpath(toolboxRoot));
assert(isempty(findobj('Tag','CCEPGUIMainFig')), 'Close the CCEP GUI: this capture uses function defaults');
diary(fullfile(outputDirectory, 'capture.log'));
cleanupDiary = onCleanup(@() diary('off')); %#ok<NASGU>
rng(1729, 'twister');
manifest.schema_version = 1;
manifest.kind = 'matlab-reference';
manifest.created_utc = datestr(now, 30);
manifest.timestamp_basis = 'MATLAB local clock';
manifest.matlab_version = version;
manifest.computer = computer;
manifest.dependencies = ver;
manifest.expected_revision = 'a25ed5d75536e5d3a8c2570c48f3196055a7f4bd';
manifest.rng_before = rng;
manifest.sources = struct('path', {}, 'sha256', {});
names = {'CCEPSimilarityDistanceMetricsRMSOnly', 'StimPulseFinder', ...
         'CCEPStimFreqDataTimeAllocation', 'CCEPFilterFunction', ...
         'CCEPBaselineTimeGrabber', 'CCEPMakeRMSZScores'};
for n = 1:numel(names)
    file = which(names{n});
    assert(~isempty(file), ['Missing function ' names{n}]);
    manifest.sources(n).path = strrep(strrep(file, [toolboxRoot filesep], ''), filesep, '/');
    manifest.sources(n).sha256 = filehash(file);
end
manifest.stages = struct('case_id', {}, 'status', {}, 'path', {}, 'sha256', {}, 'error', {});
for caseIndex = 1:6
    item.case_id = names{caseIndex};
    if caseIndex == 6, item.case_id = 'ranksum'; end
    item.status = 'failed'; item.path = ''; item.sha256 = ''; item.error = '';
    try
        values = struct;
        switch caseIndex
            case 1
                values.response = [3 4; 0 0; Inf 1; 2 2];
                values.baseline = [1.5 2; 0 0; 1 1; 1 1];
                info.Info.SamplingFreq = 1000;
                [distance, ~] = CCEPSimilarityDistanceMetricsRMSOnly(info, values.response, values.baseline);
                values.rms = distance.RMS; values.std = distance.StDev;
            case 2
                values.data = zeros(1,50); values.data(4:5) = 400001;
                values.data(9:10) = 900000; values.data(21:25) = 400000;
                values.data(31:35) = 500000;
                values.pulses_one_based = StimPulseFinder(values.data);
            case 3
                values.frequencies = [.5 5.04 5.06 39 40];
                info.Info.SamplingFreq = 1000;
                for j = 1:numel(values.frequencies)
                    stim.Frequency = values.frequencies(j);
                    [values.windows(j,1), values.windows(j,2), values.windows(j,3)] = CCEPStimFreqDataTimeAllocation(info, stim, 1);
                end
            case 4
                assert(exist('fir1','file') ~= 0, 'Signal Processing Toolbox required');
                values.sampling_hz = 1000;
                values.data = sin((0:4095)*.03) + cos((0:4095)*.17);
                info.Info.SamplingFreq = 1000; info.Uni.Label = 'A1';
                imported.Label = 'A1'; imported.Data = values.data;
                [~, output] = CCEPFilterFunction(info, imported, 'Uni');
                values.filtered_uni = output.Data;
                [~, output] = CCEPFilterFunction(info, imported, 'Bi');
                values.filtered_bi = output.Data;
                values.band_coefficients = fir1(500,[1/500,300/500]);
                values.notch_coefficients = fir1(500,[48/500/500,52/500/500],'stop');
            case 5
                info.Info.SamplingFreq = 1000;
                info.Info.DataFile = 'synthetic';
                imported.Data = zeros(1,30000);
                annotation.Times = 15001; annotation.Comment = 'mark';
                stim.TimeWindow = [20001 21001];
                values.sampling_hz = 1000; values.samples = 30000;
                values.annotation_samples_one_based = 15001;
                values.annotation_text = {'mark'};
                values.train_windows_one_based = [20001 21001];
                values.window_samples = 200;
                values.rng_before = rng;
                values.windows_one_based = CCEPBaselineTimeGrabber('Info',info,'Stim',stim,'Annotations',annotation,'Signal',imported,'NumBaselines',8,'Window',200);
                values.rng_after = rng;
            case 6
                assert(exist('ranksum','file') ~= 0, 'Statistics Toolbox required');
                values.actual = 20:29; values.baseline = 0:9;
                [values.p, ~, stats] = ranksum(values.actual,values.baseline);
                values.z = stats.zval;
                [~, ~, values.small_stats] = ranksum(0:5,0:5);
        end
        item.path = [item.case_id '.mat'];
        save(fullfile(outputDirectory,item.path), '-struct', 'values', '-v6');
        item.sha256 = filehash(fullfile(outputDirectory,item.path));
        item.status = 'success';
    catch failure
        item.error = getReport(failure, 'extended', 'hyperlinks', 'off');
        fprintf(2, '%s\n', item.error);
    end
    manifest.stages(caseIndex) = item;
end
manifest.rng_after = rng;
fid = fopen(fullfile(outputDirectory,'manifest.json'),'w');
assert(fid ~= -1, 'Cannot write manifest');
cleanupFile = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid, '%s\n', jsonencode(manifest));
end

function value = filehash(filename)
fid = fopen(filename, 'rb'); assert(fid ~= -1, 'Cannot hash file');
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
digest = java.security.MessageDigest.getInstance('SHA-256');
while ~feof(fid)
    block = fread(fid, 1024*1024, '*uint8');
    digest.update(typecast(block, 'int8'));
end
value = lower(reshape(dec2hex(typecast(digest.digest(), 'uint8'),2)',1,[]));
end
